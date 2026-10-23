"""Soft batch deletion fences existing entrypoints and late worker commits."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from .content_helpers import draft, key, picture, process_jobs, publish, recording
from .test_import_removal import make_batch, save_batch
from .test_imports import document
from .test_multi_zip_imports import upload_zip


def delete(admin, batch, *, headers=None):
    return admin.request(
        "DELETE",
        f"/api/admin/v1/imports/{batch['id']}",
        headers=headers or key(),
        json={"expected_updated_at": batch["updated_at"]},
    )


def test_delete_batch_preserves_saved_cards_media_and_original_receipts(admin, mini, system):
    from juya_api.content_models import Card, Media
    from juya_api.import_models import ImportBatch, ImportFile, ImportItem

    batch = make_batch(admin)
    upload_zip(
        admin,
        batch["id"],
        "retained.zip",
        [
            ("场景/内容.docx", document("保留已存卡片")),
            ("场景/图片.png", picture()),
            ("场景/音频.wav", recording()),
        ],
    )
    process_jobs(admin)
    batch = save_batch(admin, batch["id"])
    card_id = batch["items"][0]["saved_card_id"]
    card = publish(admin, admin.get(f"/api/admin/v1/cards/{card_id}").json())
    shared = draft(admin, card["content"])
    completed = mini.post(
        f"/api/mini/v1/cards/{card_id}/complete",
        headers=key(),
        json={"version_id": card["current_version_id"]},
    )
    assert completed.status_code == 200, completed.text
    statistics = mini.get("/api/mini/v1/me/statistics").json()
    with system["sessions"]() as db:
        media = db.scalar(select(func.count()).select_from(Media))
        assert media > 0
        file_count = db.scalar(select(func.count()).select_from(ImportFile))
    headers = key()
    removed = delete(admin, batch, headers=headers)
    assert removed.status_code == 200, removed.text
    assert removed.json() == {"id": batch["id"], "deleted": True}
    assert delete(admin, batch, headers=headers).json() == removed.json()
    assert (
        admin.get("/api/admin/v1/operations/" + headers["Idempotency-Key"]).json()["result"]
        == removed.json()
    )
    assert delete(admin, batch).status_code == 404
    for suffix in ["", "?require_resumable=true", "/confirmation"]:
        assert admin.get(f"/api/admin/v1/imports/{batch['id']}" + suffix).status_code == 404
    for suffix in ["", "?resumable_only=true"]:
        assert batch["id"] not in {
            value["id"] for value in admin.get("/api/admin/v1/imports" + suffix).json()
        }
    assert admin.get(f"/api/admin/v1/cards/{card_id}").status_code == 200
    assert admin.get(f"/api/admin/v1/cards/{shared['id']}").json()["content"] == card["content"]
    assert mini.get(f"/api/mini/v1/cards/{card_id}").status_code == 200
    assert mini.get("/api/mini/v1/me/statistics").json() == statistics
    assert mini.get("/api/mini/v1/me/learning-records").json()["total"] == 1
    with system["sessions"]() as db:
        assert db.get(ImportBatch, batch["id"]).deleted_at is not None
        assert db.get(Card, card_id).deleted_at is None
        assert db.scalar(select(func.count()).select_from(Media)) == media
        assert db.scalar(select(func.count()).select_from(ImportFile)) == file_count
        assert db.get(ImportItem, batch["items"][0]["id"]).saved_card_id == card_id


def test_delete_checks_auth_csrf_owner_and_raw_displayed_version(admin, mini, system):
    from juya_api.import_models import ImportBatch
    from juya_api.models import Administrator

    batch = make_batch(admin, "版本检查")
    assert delete(admin, batch, headers={**key(), "X-CSRF-Token": "bad"}).status_code == 403
    assert (
        mini.request(
            "DELETE",
            f"/api/admin/v1/imports/{batch['id']}",
            headers=key(),
            json={"expected_updated_at": batch["updated_at"]},
        ).status_code
        == 404
    )
    system["time"][0] += timedelta(seconds=1)
    item = batch["items"][0]
    admin.patch(
        f"/api/admin/v1/imports/{batch['id']}/items/{item['id']}",
        headers=key(),
        json={"revision": item["revision"], "content": item["content"], "selected": False},
    )
    stale = delete(admin, batch)
    assert stale.status_code == 409, stale.text
    assert stale.json()["error"]["code"] == "import_changed"
    with system["sessions"].begin() as db:
        other = Administrator(username="other", password_hash="fixture-only")
        db.add(other)
        db.flush()
        db.get(ImportBatch, batch["id"]).admin_id = other.id
    assert delete(admin, batch).status_code == 404
    assert (
        admin.request(
            "DELETE",
            "/api/admin/v1/imports/missing",
            headers=key(),
            json={"expected_updated_at": batch["updated_at"]},
        ).status_code
        == 404
    )


def test_same_clock_review_change_invalidates_delete_version(admin):
    batch = make_batch(admin, "同刻核对")
    item = batch["items"][0]
    changed = admin.patch(
        f"/api/admin/v1/imports/{batch['id']}/items/{item['id']}",
        headers=key(),
        json={"revision": item["revision"], "content": item["content"], "selected": False},
    )
    assert changed.status_code == 200
    assert delete(admin, batch).status_code == 409


def test_same_clock_job_progress_invalidates_delete_version(admin, system):
    from juya_api.import_service import parse_progress
    from juya_api.jobs import claim

    batch = make_batch(admin)
    root = upload_zip(
        admin, batch["id"], "progress.zip", [("场景/内容.docx", document("解析活动"))]
    )
    sessions, settings, now = system["sessions"], system["settings"], admin.app.state.clock()
    job = claim(sessions, root["job_id"], now, settings=settings)
    current = admin.get(f"/api/admin/v1/imports/{batch['id']}").json()
    parse_progress(sessions, job, now, "parsing", 1, 2)
    assert delete(admin, current).status_code == 409


def test_upload_that_passed_preflight_before_deletion_rechecks_at_final_write(
    admin, system, monkeypatch
):
    from io import BytesIO
    from types import SimpleNamespace

    from fastapi import UploadFile

    from juya_api import import_api
    from juya_api.errors import DomainError
    from juya_api.models import Administrator

    batch = make_batch(admin)
    original = import_api.operate

    def delete_after_preflight(db, actor, role, operation_key, action, *args):
        if action.startswith("import.file:"):
            db.commit()
            assert delete(admin, batch).status_code == 200
        return original(db, actor, role, operation_key, action, *args)

    route = next(
        route.endpoint
        for route in import_api.routes().routes
        if route.path == "/api/admin/v1/imports/{batch_id}/files"
    )
    monkeypatch.setattr(import_api, "operate", delete_after_preflight)
    with system["sessions"]() as db:
        db.info["settings"] = system["settings"]
        actor = db.scalar(select(Administrator))
        with pytest.raises(DomainError, match="import_missing"):
            route(
                batch["id"],
                SimpleNamespace(app=admin.app),
                "zip",
                UploadFile(filename="late.zip", file=BytesIO(b"late-file")),
                admin=actor,
                key=key()["Idempotency-Key"],
                db=db,
            )
        db.rollback()


def test_import_speech_that_passed_preflight_before_deletion_cannot_enqueue(
    admin, system, monkeypatch
):
    from types import SimpleNamespace

    from juya_api import pronunciation_api
    from juya_api.errors import DomainError
    from juya_api.models import Administrator
    from juya_api.pronunciation_api import ImportSpeechReference

    batch = make_batch(admin, "失效发音")
    item = batch["items"][0]
    word = item["content"]["vocabulary"][0]["id"]
    original = pronunciation_api.operate

    def delete_after_preflight(db, actor, role, operation_key, action, *args):
        db.commit()
        assert delete(admin, batch).status_code == 200
        return original(db, actor, role, operation_key, action, *args)

    route = next(
        route.endpoint
        for route in pronunciation_api.routes("admin").routes
        if route.path
        == "/api/admin/v1/imports/{batch_id}/items/{item_id}/words/{word_id}/pronunciation"
        and "POST" in route.methods
    )
    monkeypatch.setattr(pronunciation_api, "operate", delete_after_preflight)
    with system["sessions"]() as db:
        db.info["settings"] = system["settings"]
        actor = db.scalar(select(Administrator))
        with pytest.raises(DomainError, match="import_missing"):
            route(
                batch["id"],
                item["id"],
                word,
                ImportSpeechReference(revision=item["revision"]),
                SimpleNamespace(app=admin.app),
                actor=actor,
                key=key()["Idempotency-Key"],
                db=db,
            )
        db.rollback()


@pytest.mark.parametrize("state", ["queued", "running", "retry"])
def test_delete_rejects_accepted_save_in_progress(admin, system, state):
    from juya_api.job_models import Job

    batch = make_batch(admin, "保存保护")
    endpoint = f"/api/admin/v1/imports/{batch['id']}"
    confirmation = admin.get(endpoint + "/confirmation").json()
    accepted = admin.post(
        endpoint + "/save",
        headers=key(),
        json={"confirmed": True, "version": confirmation["version"]},
    ).json()
    with system["sessions"].begin() as db:
        db.get(Job, accepted["items"][0]["job_id"]).state = state
    response = delete(admin, admin.get(endpoint).json())
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "import_saving"
    assert admin.get(endpoint).status_code == 200


def test_deleted_batch_blocks_all_old_mutation_entrypoints(admin):
    batch = make_batch(admin, "失效入口")
    endpoint = f"/api/admin/v1/imports/{batch['id']}"
    confirmation = admin.get(endpoint + "/confirmation").json()
    assert delete(admin, batch).status_code == 200
    item, root = batch["items"][0], batch["files"][0]
    requests = [
        ("POST", "/resolve", {}),
        ("POST", "/files/" + root["id"] + "/retry", {}),
        ("POST", "/save", {"confirmed": True, "version": confirmation["version"]}),
        ("POST", "/files/remove", {"file_ids": [root["id"]]}),
        ("POST", "/items/remove", {"items": [{"id": item["id"], "revision": item["revision"]}]}),
        (
            "PATCH",
            "/items/" + item["id"],
            {"revision": item["revision"], "content": item["content"], "selected": True},
        ),
    ]
    for method, suffix, body in requests:
        response = admin.request(method, endpoint + suffix, headers=key(), json=body)
        assert response.status_code == 404, response.text
    response = admin.post(
        endpoint + "/files?kind=zip",
        headers=key(),
        files={"file": ("late.zip", picture(), "application/zip")},
    )
    assert response.status_code == 404, response.text


def test_deleted_batch_cannot_be_revived_by_late_parse_commit_or_progress(admin, system):
    from juya_api.errors import DomainError
    from juya_api.import_models import ImportItem
    from juya_api.import_service import parse_progress, prepare_parse
    from juya_api.jobs import claim, finish

    batch = make_batch(admin)
    root = upload_zip(admin, batch["id"], "late.zip", [("场景/内容.docx", document("晚到解析"))])
    settings, sessions, now = system["settings"], system["sessions"], admin.app.state.clock()
    job = claim(sessions, root["job_id"], now, settings=settings)
    result, apply = prepare_parse(settings, sessions, job, clock=lambda: now)
    current = admin.get(f"/api/admin/v1/imports/{batch['id']}").json()
    removed = delete(admin, current)
    assert removed.status_code == 200, removed.text
    with pytest.raises(DomainError, match="import_missing"):
        finish(sessions, job["id"], job["lease"], now, result, apply=apply)
    with pytest.raises(DomainError, match="import_missing"):
        parse_progress(sessions, job, now, "parsing", 1, 1)
    process_jobs(admin)
    with sessions() as db:
        assert not db.scalar(select(ImportItem).where(ImportItem.batch_id == batch["id"]))


def test_save_final_commit_rechecks_batch_even_if_worker_was_prepared(admin, system):
    from juya_api.errors import DomainError
    from juya_api.import_models import ImportBatch
    from juya_api.import_service import prepare_save
    from juya_api.jobs import claim, finish

    batch = make_batch(admin, "晚到保存")
    endpoint = f"/api/admin/v1/imports/{batch['id']}"
    confirmation = admin.get(endpoint + "/confirmation").json()
    accepted = admin.post(
        endpoint + "/save",
        headers=key(),
        json={"confirmed": True, "version": confirmation["version"]},
    ).json()
    settings, sessions, now = system["settings"], system["sessions"], admin.app.state.clock()
    job = claim(sessions, accepted["items"][0]["job_id"], now, settings=settings)
    result, apply = prepare_save(settings, sessions, job, now)
    # Defensive final check also covers an older process / interrupted delete transaction.
    with sessions.begin() as db:
        db.get(ImportBatch, batch["id"]).deleted_at = now
    with pytest.raises(DomainError, match="import_missing"):
        finish(sessions, job["id"], job["lease"], now, result, apply=apply)
    assert admin.get("/api/admin/v1/cards").json()["total"] == 0
