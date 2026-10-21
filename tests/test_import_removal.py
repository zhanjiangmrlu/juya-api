"""Deleted cards and discarded staging must never block unrelated imports."""

import pytest

from .content_helpers import key, process_jobs
from .test_imports import document
from .test_multi_zip_imports import upload_zip


def make_batch(admin, *names):
    """Create independent ZIP sources with recoverable text-only cards."""
    batch = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()
    for name in names:
        upload_zip(admin, batch["id"], name + ".zip", [(name + "/内容.docx", document(name))])
    process_jobs(admin)
    return admin.get(f"/api/admin/v1/imports/{batch['id']}").json()


def save_batch(admin, batch_id):
    """Save the server-confirmed scope, settling its durable worker tasks."""
    confirmation = admin.get(f"/api/admin/v1/imports/{batch_id}/confirmation").json()
    response = admin.post(
        f"/api/admin/v1/imports/{batch_id}/save",
        headers=key(),
        json={"confirmed": True, "version": confirmation["version"]},
    )
    assert response.status_code == 200, response.text
    process_jobs(admin)
    return admin.get(f"/api/admin/v1/imports/{batch_id}").json()


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("same_batch", [False, True])
def test_deleted_identity_allows_a_new_draft(admin, system, legacy, same_batch):
    from juya_api.import_models import ImportIdentity, ImportItem
    from juya_api.import_service import object_key
    from juya_api.security import fingerprint

    entries = [("重新导入/内容.docx", document("重新导入"))]
    first = make_batch(admin)
    upload_zip(admin, first["id"], "重新导入.zip", entries)
    process_jobs(admin)
    saved = save_batch(admin, first["id"])["items"][0]
    old_id = saved["saved_card_id"]
    if legacy:
        with system["sessions"].begin() as db:
            identity = db.get(ImportIdentity, object_key(db, db.get(ImportItem, saved["id"])))
            db.add(
                ImportIdentity(
                    object_key=fingerprint({"incomplete_item": saved["id"]}),
                    card_id=old_id,
                    content_hash=identity.content_hash,
                    draft_revision=identity.draft_revision,
                )
            )
            db.delete(identity)
    response = admin.request(
        "DELETE",
        f"/api/admin/v1/cards/{old_id}",
        headers=key(),
        json={"revision": saved["saved_draft_revision"]},
    )
    assert response.status_code == 200
    if same_batch:
        batch = admin.get(f"/api/admin/v1/imports/{first['id']}").json()
    else:
        batch = make_batch(admin)
        upload_zip(admin, batch["id"], "重命名.zip", entries)
        process_jobs(admin)
        batch = admin.get(f"/api/admin/v1/imports/{batch['id']}").json()
    assert batch["items"][0]["state"] == "incomplete"
    assert batch["items"][0]["suggested_target_id"] is None
    current = save_batch(admin, batch["id"])["items"][0]
    assert current["state"] == "saved"
    assert current["saved_card_id"] != old_id
    assert admin.get(f"/api/admin/v1/cards/{old_id}").status_code == 410
    assert admin.get("/api/admin/v1/cards").json()["total"] == 1
    third = make_batch(admin)
    upload_zip(admin, third["id"], "third.zip", entries)
    process_jobs(admin)
    duplicate = admin.get(f"/api/admin/v1/imports/{third['id']}").json()["items"][0]
    assert duplicate["state"] == "duplicate"
    assert duplicate["suggested_target_id"] == current["saved_card_id"]


def test_explicit_update_deleted_after_confirmation_is_not_converted_to_new(admin):
    first = make_batch(admin, "明确更新")
    original = save_batch(admin, first["id"])["items"][0]
    batch = make_batch(admin, "另一次导入")
    item = batch["items"][0]
    staged = admin.patch(
        f"/api/admin/v1/imports/{batch['id']}/items/{item['id']}",
        headers=key(),
        json={
            "revision": item["revision"],
            "content": item["content"],
            "selected": True,
            "target_card_id": original["saved_card_id"],
            "target_revision": original["saved_draft_revision"],
            "update_confirmed": True,
        },
    )
    assert staged.status_code == 200
    admin.request(
        "DELETE",
        f"/api/admin/v1/cards/{original['saved_card_id']}",
        headers=key(),
        json={"revision": original["saved_draft_revision"]},
    )
    failed = save_batch(admin, batch["id"])["items"][0]
    assert failed["state"] == "failed"
    assert failed["error_code"] == "card_deleted"
    assert admin.get("/api/admin/v1/cards").json()["total"] == 0


def test_remove_zip_is_idempotent_and_preserves_siblings_and_confirmation(admin):
    batch = make_batch(admin, "第一包", "第二包", "第三包")
    root = next(file for file in batch["files"] if file["name"] == "第二包.zip")
    before = admin.get(f"/api/admin/v1/imports/{batch['id']}/confirmation").json()
    endpoint = f"/api/admin/v1/imports/{batch['id']}/files/remove"
    operation = key()
    removed = admin.post(endpoint, headers=operation, json={"file_ids": [root["id"]]})
    assert removed.status_code == 200, removed.text
    result = removed.json()
    assert {item["content"]["name"] for item in result["items"]} == {"第一包", "第三包"}
    assert not any(
        file["id"] == root["id"] or file["parent_id"] == root["id"] for file in result["files"]
    )
    assert admin.post(endpoint, headers=operation, json={"file_ids": [root["id"]]}).json() == result
    stale = admin.post(
        f"/api/admin/v1/imports/{batch['id']}/save",
        headers=key(),
        json={"version": before["version"], "confirmed": True},
    )
    assert stale.status_code == 409
    assert len(save_batch(admin, batch["id"])["items"]) == 2
    assert admin.get("/api/admin/v1/cards").json()["total"] == 2


def test_remove_multiple_items_retains_same_zip_and_other_folders(admin):
    batch = make_batch(admin)
    upload_zip(
        admin,
        batch["id"],
        "three.zip",
        [(f"{i}/内容.docx", document(f"卡片{i}")) for i in range(3)],
    )
    process_jobs(admin)
    batch = admin.get(f"/api/admin/v1/imports/{batch['id']}").json()
    selected = [{"id": item["id"], "revision": item["revision"]} for item in batch["items"][:2]]
    response = admin.post(
        f"/api/admin/v1/imports/{batch['id']}/items/remove", headers=key(), json={"items": selected}
    )
    assert response.status_code == 200, response.text
    assert [item["content"]["name"] for item in response.json()["items"]] == ["卡片2"]
    assert len(response.json()["files"]) == len(batch["files"])
    save_batch(admin, batch["id"])
    assert admin.get("/api/admin/v1/cards").json()["total"] == 1


@pytest.mark.parametrize("kind", ["files", "items"])
def test_removal_rejects_saved_or_accepted_save_without_partial_deletion(admin, kind):
    batch = make_batch(admin, "保留保存结果", "未保存")
    first, second = batch["items"]
    admin.patch(
        f"/api/admin/v1/imports/{batch['id']}/items/{second['id']}",
        headers=key(),
        json={"revision": second["revision"], "content": second["content"], "selected": False},
    )
    confirmation = admin.get(f"/api/admin/v1/imports/{batch['id']}/confirmation").json()
    admin.post(
        f"/api/admin/v1/imports/{batch['id']}/save",
        headers=key(),
        json={"version": confirmation["version"], "confirmed": True},
    )
    endpoint = f"/api/admin/v1/imports/{batch['id']}/{kind}/remove"
    body = (
        {"file_ids": [item["source_zip_id"] for item in batch["items"]]}
        if kind == "files"
        else {"items": [{"id": first["id"], "revision": first["revision"]}]}
    )
    assert admin.post(endpoint, headers=key(), json=body).status_code == 409
    process_jobs(admin)
    assert admin.post(endpoint, headers=key(), json=body).status_code == 409
    assert len(admin.get(f"/api/admin/v1/imports/{batch['id']}").json()["items"]) == 2
    assert admin.get("/api/admin/v1/cards").json()["total"] == 1


def test_removal_revision_and_batch_membership_are_checked_atomically(admin):
    batch = make_batch(admin, "甲", "乙")
    other = make_batch(admin, "丙")
    endpoint = f"/api/admin/v1/imports/{batch['id']}/items/remove"
    first, second = batch["items"]
    response = admin.post(
        endpoint,
        headers=key(),
        json={"items": [{"id": first["id"], "revision": 1}, {"id": second["id"], "revision": 99}]},
    )
    assert response.status_code == 409
    response = admin.post(
        endpoint,
        headers=key(),
        json={
            "items": [
                {"id": first["id"], "revision": 1},
                {"id": other["items"][0]["id"], "revision": 1},
            ]
        },
    )
    assert response.status_code == 404
    assert len(admin.get(f"/api/admin/v1/imports/{batch['id']}").json()["items"]) == 2


def test_removed_zip_cannot_be_rebuilt_by_a_late_parse_and_can_be_uploaded_again(admin, system):
    from juya_api.errors import DomainError
    from juya_api.import_service import prepare_parse
    from juya_api.jobs import claim, finish

    batch = make_batch(admin)
    entries = [("场景/内容.docx", document("移除解析中的ZIP"))]
    root = upload_zip(admin, batch["id"], "running.zip", entries)
    app = admin.app
    now = app.state.clock()
    job = claim(system["sessions"], root["job_id"], now, settings=app.state.settings)
    result, apply = prepare_parse(app.state.settings, system["sessions"], job, clock=lambda: now)
    removed = admin.post(
        f"/api/admin/v1/imports/{batch['id']}/files/remove",
        headers=key(),
        json={"file_ids": [root["id"]]},
    )
    assert removed.status_code == 200, removed.text
    with pytest.raises(DomainError, match="import_changed"):
        finish(system["sessions"], root["job_id"], job["lease"], now, result, apply=apply)
    assert admin.get(f"/api/admin/v1/imports/{batch['id']}").json()["items"] == []
    again = upload_zip(admin, batch["id"], "running.zip", entries)
    assert again["id"] != root["id"]
    process_jobs(admin)
    assert len(admin.get(f"/api/admin/v1/imports/{batch['id']}").json()["items"]) == 1


def test_removal_checks_owner_and_csrf(admin, system):
    from juya_api.import_models import ImportBatch
    from juya_api.models import Administrator

    batch = make_batch(admin, "归属检查")
    endpoint = f"/api/admin/v1/imports/{batch['id']}/files/remove"
    body = {"file_ids": [batch["items"][0]["source_zip_id"]]}
    assert (
        admin.post(endpoint, headers={**key(), "X-CSRF-Token": "invalid"}, json=body).status_code
        == 403
    )
    with system["sessions"].begin() as db:
        owner = Administrator(username="another", password_hash="unused-fixture")
        db.add(owner)
        db.flush()
        db.get(ImportBatch, batch["id"]).admin_id = owner.id
    assert admin.post(endpoint, headers=key(), json=body).status_code == 404


def test_removal_accepts_all_zip_roots_even_when_failures_exceed_the_card_limit(admin, system):
    from juya_api.import_models import ImportFile
    from juya_api.models import identifier

    batch = make_batch(admin)
    ids = []
    with system["sessions"].begin() as db:
        for number in range(51):
            file_id = identifier()
            ids.append(file_id)
            db.add(
                ImportFile(
                    id=file_id,
                    batch_id=batch["id"],
                    parent_id="",
                    kind="zip",
                    name=f"broken-{number}.zip",
                    size=10,
                    storage_key="unused-test-source",
                    sha256=f"{number:064x}",
                    error_code="archive_unsafe",
                    created_at=admin.app.state.clock(),
                )
            )
    response = admin.post(
        f"/api/admin/v1/imports/{batch['id']}/files/remove", headers=key(), json={"file_ids": ids}
    )
    assert response.status_code == 200, response.text
    assert response.json()["files"] == []


@pytest.mark.mysql
def test_mysql_remove_and_late_parse_commit_leave_no_recreated_items(admin, system):
    """The final source check must share the same actor lock as source removal."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from juya_api.errors import DomainError
    from juya_api.import_service import prepare_parse
    from juya_api.jobs import claim, finish

    if system["engine"].dialect.name != "mysql":
        pytest.skip("Real MySQL actor serialization")
    batch = make_batch(admin)
    root = upload_zip(
        admin, batch["id"], "race.zip", [("卡片/内容.docx", document("解析并发移除"))]
    )
    settings, sessions, now = admin.app.state.settings, system["sessions"], admin.app.state.clock()
    job = claim(sessions, root["job_id"], now, settings=settings)
    result, apply = prepare_parse(settings, sessions, job, clock=lambda: now)
    barrier = Barrier(2)

    def complete():
        barrier.wait(timeout=10)
        try:
            return finish(sessions, job["id"], job["lease"], now, result, apply=apply)
        except DomainError as error:
            assert error.code == "import_changed"
            return False

    def remove():
        barrier.wait(timeout=10)
        return admin.post(
            f"/api/admin/v1/imports/{batch['id']}/files/remove",
            headers=key(),
            json={"file_ids": [root["id"]]},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        completed = pool.submit(complete)
        removed = pool.submit(remove)
        assert removed.result(timeout=60).status_code == 200
        assert completed.result(timeout=60) in {True, False}
    current = admin.get(f"/api/admin/v1/imports/{batch['id']}").json()
    assert current["files"] == []
    assert current["items"] == []


@pytest.mark.mysql
def test_mysql_remove_and_save_acceptance_have_one_winner(admin, system):
    """A save accepted first is protected; a removal accepted first invalidates save scope."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    if system["engine"].dialect.name != "mysql":
        pytest.skip("Real MySQL actor serialization")
    batch = make_batch(admin, "保存并发移除")
    confirmation = admin.get(f"/api/admin/v1/imports/{batch['id']}/confirmation").json()
    barrier = Barrier(2)

    def send(path, body):
        barrier.wait(timeout=10)
        return admin.post(f"/api/admin/v1/imports/{batch['id']}/{path}", headers=key(), json=body)

    with ThreadPoolExecutor(max_workers=2) as pool:
        save = pool.submit(send, "save", {"version": confirmation["version"], "confirmed": True})
        remove = pool.submit(
            send, "files/remove", {"file_ids": [batch["items"][0]["source_zip_id"]]}
        )
        assert sorted(
            [save.result(timeout=60).status_code, remove.result(timeout=60).status_code]
        ) == [200, 409]
    process_jobs(admin)
    current = admin.get(f"/api/admin/v1/imports/{batch['id']}").json()
    count = admin.get("/api/admin/v1/cards").json()["total"]
    assert (len(current["items"]), count) in {(0, 0), (1, 1)}
    assert all(item["state"] == "saved" for item in current["items"])
