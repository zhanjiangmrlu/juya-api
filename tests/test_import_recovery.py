"""CHG-0022 restores durable unfinished work, never a recent-history guess."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from juya_api.import_models import ImportBatch, ImportFile
from juya_api.job_models import Job
from juya_api.storage import ObjectStorage

from .content_helpers import key, picture, process_jobs, recording
from .test_imports import document


def uploaded(admin, name="资料.docx", data=None, kind="docx"):
    batch = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "docx"}).json()
    response = admin.post(
        f"/api/admin/v1/imports/{batch['id']}/files?kind={kind}",
        headers=key(),
        files={"file": (name, data or document(name), "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    return batch["id"], response.json()


def recovery(admin, batch_id):
    return admin.get(f"/api/admin/v1/imports/{batch_id}?require_resumable=true")


def pending(admin):
    response = admin.get("/api/admin/v1/imports?resumable_only=true")
    assert response.status_code == 200, response.text
    return response.json()


def save(admin, batch_id):
    confirmation = admin.get(f"/api/admin/v1/imports/{batch_id}/confirmation").json()
    response = admin.post(
        f"/api/admin/v1/imports/{batch_id}/save",
        headers=key(),
        json={"confirmed": True, "version": confirmation["version"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_batches_and_local_only_inputs_are_not_recoverable(admin):
    empty = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()
    assert pending(admin) == []
    assert recovery(admin, empty["id"]).status_code == 409
    # Ordinary history and a current empty upload remain readable.
    assert admin.get("/api/admin/v1/imports").json()[0]["id"] == empty["id"]
    assert admin.get(f"/api/admin/v1/imports/{empty['id']}").status_code == 200


def test_recoverable_collection_has_no_recent_five_limit_and_is_owner_scoped(admin, system):
    ids = [uploaded(admin, f"批次{index}.docx")[0] for index in range(7)]
    from juya_api.models import Administrator

    with system["sessions"].begin() as db:
        other = Administrator(username="other", password_hash="unused-fixture-password")
        db.add(other)
        db.flush()
        db.get(ImportBatch, ids[-1]).admin_id = other.id
    assert {row["id"] for row in pending(admin)} == set(ids[:-1])
    assert len(admin.get("/api/admin/v1/imports").json()) == 5
    denied = recovery(admin, ids[-1])
    assert denied.status_code == 409
    assert denied.json()["error"]["code"] == "import_not_resumable"
    assert recovery(admin, "missing-batch").status_code == 409


def test_stage_names_and_time_follow_real_upload_parse_review_and_save(admin, system):
    batch_id, _ = uploaded(admin, "原始来源.docx")
    initial = recovery(admin, batch_id).json()
    assert initial["resumable"] and initial["stage"] == "processing"
    assert initial["source_names"] == ["原始来源.docx"]
    system["time"][0] += timedelta(minutes=2)
    process_jobs(admin)
    review = recovery(admin, batch_id).json()
    assert review["stage"] == "review"
    assert review["updated_at"] > initial["updated_at"]
    system["time"][0] += timedelta(minutes=2)
    item = review["items"][0]
    staged = admin.patch(
        f"/api/admin/v1/imports/{batch_id}/items/{item['id']}",
        headers=key(),
        json={
            "revision": item["revision"],
            "content": dict(item["content"], name="已核对的标题"),
            "selected": False,
        },
    )
    assert staged.status_code == 200
    staged_batch = recovery(admin, batch_id).json()
    assert staged_batch["updated_at"] > review["updated_at"]
    assert staged_batch["items"][0]["selected"] is False
    # Reads do not manufacture a new update time.
    system["time"][0] += timedelta(minutes=2)
    assert recovery(admin, batch_id).json()["updated_at"] == staged_batch["updated_at"]


def test_uploaded_attachment_without_document_recovers_upload_stage(admin):
    batch_id, _ = uploaded(admin, "配套图.png", picture(), "image")
    process_jobs(admin)
    value = recovery(admin, batch_id).json()
    assert value["resumable"] and value["stage"] == "upload"
    assert value["source_names"] == ["配套图.png"]


@pytest.mark.parametrize("running", [False, True])
def test_missing_unparsed_source_is_not_recoverable_even_with_a_worker_lease(
    admin, system, running
):
    batch_id, file = uploaded(admin)
    with system["sessions"].begin() as db:
        source = db.get(ImportFile, file["id"])
        ObjectStorage(system["settings"]).path(source.storage_key).unlink()
        if running:
            job = db.get(Job, source.job_id)
            job.state, job.lease = "running", "live-lease"
            job.lease_expires_at = system["time"][0].replace(tzinfo=None) + timedelta(minutes=5)
    assert pending(admin) == []
    assert recovery(admin, batch_id).status_code == 409
    assert admin.get(f"/api/admin/v1/imports/{batch_id}").status_code == 200


def test_persisted_review_survives_missing_original_and_keeps_input(admin, system):
    batch_id, file = uploaded(admin)
    process_jobs(admin)
    with system["sessions"]() as db:
        source = db.get(ImportFile, file["id"])
        ObjectStorage(system["settings"]).path(source.storage_key).unlink()
    result = recovery(admin, batch_id)
    assert result.status_code == 200
    assert result.json()["stage"] == "review"
    assert result.json()["items"][0]["content"]["dialogue"]


def test_completed_and_duplicate_batches_drop_from_recovery_without_deleting_drafts(admin, mini):
    data = document("同一份卡片")
    first, _ = uploaded(admin, data=data)
    process_jobs(admin)
    saving = save(admin, first)
    assert saving["resumable"] and saving["stage"] == "result"
    process_jobs(admin)
    assert recovery(admin, first).status_code == 409
    result = admin.get(f"/api/admin/v1/imports/{first}").json()
    assert not result["resumable"] and result["stage"] == "result"
    assert result["items"][0]["state"] == "saved"
    second, _ = uploaded(admin, data=data)
    process_jobs(admin)
    assert pending(admin) == []
    assert recovery(admin, second).status_code == 409
    assert admin.get("/api/admin/v1/cards").json()["total"] == 1
    assert mini.get("/api/mini/v1/cards").json()["total"] == 0


@pytest.mark.parametrize(
    "error,recoverable", [("worker_interrupted", True), ("docx_invalid", False)]
)
def test_only_applicable_parse_failures_are_recoverable(admin, system, error, recoverable):
    batch_id, file = uploaded(admin)
    with system["sessions"].begin() as db:
        job = db.get(Job, file["job_id"])
        job.state, job.error_code = "failed", error
    response = recovery(admin, batch_id)
    assert response.status_code == (200 if recoverable else 409)
    assert bool(pending(admin)) is recoverable


def test_mixed_results_recover_failed_save_and_do_not_duplicate_success(admin, system):
    batch_id, _ = uploaded(admin, data=document("已成功", "待重试"))
    process_jobs(admin)
    accepted = save(admin, batch_id)
    from juya_api.worker import run_job

    run_job(
        system["settings"],
        system["sessions"],
        accepted["items"][0]["job_id"],
        clock=admin.app.state.clock,
    )
    with system["sessions"].begin() as db:
        job = db.get(Job, accepted["items"][1]["job_id"])
        job.state, job.error_code = "failed", "worker_interrupted"
    restored = recovery(admin, batch_id).json()
    assert restored["stage"] == "result"
    assert [row["state"] for row in restored["items"]] == ["saved", "failed"]
    assert restored["items"][0]["saved_card_id"]
    save(admin, batch_id)
    process_jobs(admin)
    assert pending(admin) == []
    assert admin.get("/api/admin/v1/cards").json()["total"] == 2
    with system["sessions"]() as db:
        assert len(db.scalars(select(Job).where(Job.kind == "import.save")).all()) == 3


def test_storage_query_failure_is_an_error_instead_of_an_empty_collection(admin, monkeypatch):
    uploaded(admin)
    from juya_api.errors import DomainError

    def unavailable(self, key):
        raise DomainError(503, "storage_unavailable", "素材暂不可用")

    monkeypatch.setattr(ObjectStorage, "exists", unavailable, raising=False)
    response = admin.get("/api/admin/v1/imports?resumable_only=true")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "storage_unavailable"


@pytest.mark.parametrize("already_read", [False, True])
def test_live_worker_missing_source_becomes_recoverable_only_after_staging_commits(
    admin, system, monkeypatch, already_read
):
    batch_id, file = uploaded(admin)
    from juya_api.worker import run_job

    read = ObjectStorage.read

    def lose_source(storage, storage_key):
        data = read(storage, storage_key) if already_read else None
        storage.path(storage_key).unlink()
        with system["sessions"]() as db:
            assert db.get(Job, file["job_id"]).state == "running"
        # A live lease alone cannot promise durable recovery if the worker then crashes.
        assert pending(admin) == []
        assert recovery(admin, batch_id).status_code == 409
        return data if already_read else read(storage, storage_key)

    monkeypatch.setattr(ObjectStorage, "read", lose_source)
    run_job(system["settings"], system["sessions"], file["job_id"], clock=admin.app.state.clock)
    assert recovery(admin, batch_id).status_code == (200 if already_read else 409)
    with system["sessions"]() as db:
        job = db.get(Job, file["job_id"])
        assert job.state == ("succeeded" if already_read else "failed")
        if not already_read:
            assert job.error_code == "media_missing"


def test_timestamp_records_retry_and_removal_without_reopening_removed_content(admin, system):
    batch_id, file = uploaded(admin)
    original = recovery(admin, batch_id).json()["updated_at"]
    with system["sessions"].begin() as db:
        job = db.get(Job, file["job_id"])
        job.state, job.error_code = "failed", "worker_interrupted"
    system["time"][0] += timedelta(minutes=1)
    retried = admin.post(
        f"/api/admin/v1/imports/{batch_id}/files/{file['id']}/retry", headers=key()
    )
    assert retried.status_code == 200
    retry_time = recovery(admin, batch_id).json()["updated_at"]
    assert retry_time > original
    process_jobs(admin)
    item = recovery(admin, batch_id).json()["items"][0]
    system["time"][0] += timedelta(minutes=1)
    removed = admin.post(
        f"/api/admin/v1/imports/{batch_id}/items/remove",
        headers=key(),
        json={"items": [{"id": item["id"], "revision": item["revision"]}]},
    )
    assert removed.status_code == 200
    assert removed.json()["updated_at"] > retry_time
    assert removed.json()["items"] == []
    assert pending(admin) == []


def test_invalid_archive_is_not_offered_as_a_retryable_recovery(admin):
    batch_id = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()["id"]
    response = admin.post(
        f"/api/admin/v1/imports/{batch_id}/files?kind=zip",
        headers=key(),
        files={"file": ("损坏资料.zip", b"not an archive", "application/zip")},
    )
    assert response.status_code == 201
    process_jobs(admin)
    assert pending(admin) == []
    assert recovery(admin, batch_id).status_code == 409
    retry = admin.post(
        f"/api/admin/v1/imports/{batch_id}/files/{response.json()['id']}/retry", headers=key()
    )
    assert retry.status_code == 422


def test_wrong_audio_extension_requires_new_source_instead_of_retrying_same_bytes(admin):
    batch_id, file = uploaded(admin, "实际WAV.mp3", recording(), "audio")
    process_jobs(admin)
    assert pending(admin) == []
    retry = admin.post(f"/api/admin/v1/imports/{batch_id}/files/{file['id']}/retry", headers=key())
    assert retry.status_code == 422


def test_parse_progress_reports_actual_task_time_without_touching_creation_time(admin, system):
    from juya_api.import_service import parse_progress
    from juya_api.jobs import claim

    batch_id, file = uploaded(admin)
    original = recovery(admin, batch_id).json()
    system["time"][0] += timedelta(minutes=1)
    now = admin.app.state.clock()
    job = claim(system["sessions"], file["job_id"], now, settings=system["settings"])
    system["time"][0] += timedelta(minutes=1)
    parse_progress(system["sessions"], job, admin.app.state.clock(), "parsing", 2, 4)
    progress = recovery(admin, batch_id).json()
    assert progress["created_at"] == original["created_at"]
    assert progress["updated_at"] == "2026-10-17T08:02:00.000000Z"
    assert progress["files"][0]["progress"] == {"phase": "parsing", "processed": 2, "total": 4}


def test_upload_refreshes_preflight_batch_after_a_later_staging_edit_commits(admin, system):
    """An earlier upload's cached preflight cannot erase a later accepted review timestamp."""
    from juya_api.dependencies import database

    batch_id, _ = uploaded(admin)
    process_jobs(admin)
    item = recovery(admin, batch_id).json()["items"][0]
    cached = system["sessions"]()
    batch = cached.get(ImportBatch, batch_id)
    cached.commit()  # Retain the preflight identity while another operation commits.
    system["time"][0] += timedelta(minutes=2)
    staged = admin.patch(
        f"/api/admin/v1/imports/{batch_id}/items/{item['id']}",
        headers=key(),
        json={"revision": item["revision"], "content": item["content"], "selected": False},
    )
    assert staged.status_code == 200
    assert batch.updated_at.strftime("%H:%M") == "08:00"
    system["time"][0] -= timedelta(minutes=1)

    def stale_preflight_session():
        cached.info["settings"] = system["settings"]
        with cached.begin():
            yield cached

    admin.app.dependency_overrides[database] = stale_preflight_session
    try:
        response = admin.post(
            f"/api/admin/v1/imports/{batch_id}/files?kind=image",
            headers=key(),
            files={"file": ("稍早发起的上传.png", picture(), "image/png")},
        )
        assert response.status_code == 201, response.text
    finally:
        admin.app.dependency_overrides.pop(database)
        cached.close()
    assert recovery(admin, batch_id).json()["updated_at"] > "2026-10-17T08:02:00.000000Z"


@pytest.mark.parametrize("accept_minute", [1, 5])
def test_delayed_stage_retains_worker_finish_time_when_unbinding_its_job(
    admin, system, monkeypatch, accept_minute
):
    """Run the real route around an actor-lock wait without claiming SQLite row concurrency."""
    from types import SimpleNamespace

    from juya_api import import_api
    from juya_api.import_api import StageItem
    from juya_api.models import Administrator
    from juya_api.worker import run_job

    batch_id, _ = uploaded(admin, data=document("完成一项", "另一项仍在保存"))
    process_jobs(admin)
    item = save(admin, batch_id)["items"][0]
    base = system["time"][0]
    system["time"][0] = base + timedelta(minutes=1)
    with system["sessions"]() as db:
        actor = db.scalar(select(Administrator))
    route = next(
        route.endpoint
        for route in import_api.routes().routes
        if route.path == "/api/admin/v1/imports/{batch_id}/items/{item_id}"
    )
    operate = import_api.operate

    def finish_before_actor_lock(*args):
        # The route already captured minute 1; its worker wins the lock and commits minute 4.
        moments = iter(base + timedelta(minutes=value) for value in (2, 3, 4))
        run_job(system["settings"], system["sessions"], item["job_id"], clock=lambda: next(moments))
        before = recovery(admin, batch_id).json()
        assert before["updated_at"] >= "2026-10-17T08:04:00.000000Z"
        assert before["resumable"]
        system["time"][0] = base + timedelta(minutes=accept_minute)
        return operate(*args)

    monkeypatch.setattr(import_api, "operate", finish_before_actor_lock)
    with system["sessions"].begin() as db:
        db.info["settings"] = system["settings"]
        route(
            batch_id,
            item["id"],
            StageItem(revision=item["revision"], content=item["content"], selected=False),
            SimpleNamespace(app=admin.app),
            admin=actor,
            key=key()["Idempotency-Key"],
            db=db,
        )
    current = recovery(admin, batch_id).json()
    assert current["resumable"]
    assert [value["state"] for value in current["items"]] == ["saved", "saving"]
    assert current["updated_at"] >= f"2026-10-17T08:0{max(4, accept_minute)}:00.000000Z"


@pytest.mark.parametrize("mutation", ["remove", "retry"])
def test_unlinking_last_source_job_keeps_its_maximum_recorded_activity(admin, system, mutation):
    from .test_imports import archive

    if mutation == "remove":
        batch_id = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()[
            "id"
        ]
        file = admin.post(
            f"/api/admin/v1/imports/{batch_id}/files?kind=zip",
            headers=key(),
            files={
                "file": (
                    "source.zip",
                    archive([("卡/内容.docx", document("卡"))]),
                    "application/zip",
                )
            },
        ).json()
    else:
        batch_id, file = uploaded(admin)
    recorded = system["time"][0].replace(tzinfo=None) + timedelta(minutes=4)
    with system["sessions"].begin() as db:
        job = db.get(Job, file["job_id"])
        job.state, job.error_code, job.updated_at = "failed", "worker_interrupted", recorded
    before = recovery(admin, batch_id).json()
    assert before["updated_at"] == "2026-10-17T08:04:00.000000Z"
    system["time"][0] += timedelta(minutes=1)
    if mutation == "remove":
        changed = admin.post(
            f"/api/admin/v1/imports/{batch_id}/files/remove",
            headers=key(),
            json={"file_ids": [file["id"]]},
        )
    else:
        changed = admin.post(
            f"/api/admin/v1/imports/{batch_id}/files/{file['id']}/retry", headers=key()
        )
    assert changed.status_code == 200, changed.text
    current = admin.get(f"/api/admin/v1/imports/{batch_id}").json()
    assert current["updated_at"] > before["updated_at"]
    with system["sessions"]() as db:
        assert db.get(ImportBatch, batch_id).updated_at > recorded


@pytest.mark.mysql
def test_mysql_progress_and_zip_removal_do_not_invert_file_and_batch_locks(admin, system):
    """Progress reserves the actor first; removal waits without holding another write lock."""
    from concurrent.futures import ThreadPoolExecutor, TimeoutError
    from threading import Event

    from sqlalchemy import event

    from juya_api.import_service import parse_progress
    from juya_api.jobs import claim

    from .test_imports import archive

    if system["engine"].dialect.name != "mysql":
        pytest.skip("Real MySQL progress/removal row lock order")
    batch_id = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()["id"]
    root = admin.post(
        f"/api/admin/v1/imports/{batch_id}/files?kind=zip",
        headers=key(),
        files={
            "file": ("并发.zip", archive([("卡片/内容.docx", document("并发"))]), "application/zip")
        },
    ).json()
    sessions, settings, engine = system["sessions"], system["settings"], system["engine"]
    now = admin.app.state.clock()
    job = claim(sessions, root["job_id"], now, settings=settings)
    system["time"][0] += timedelta(seconds=1)
    now = admin.app.state.clock()
    file_locked, release_progress = Event(), Event()

    def observe(connection, cursor, statement, parameters, context, many):
        if statement.startswith("UPDATE import_files SET"):
            file_locked.set()
            assert release_progress.wait(timeout=10)

    def remove():
        assert file_locked.wait(timeout=10)
        return admin.post(
            f"/api/admin/v1/imports/{batch_id}/files/remove",
            headers=key(),
            json={"file_ids": [root["id"]]},
        )

    event.listen(engine, "after_cursor_execute", observe)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            progress = pool.submit(parse_progress, sessions, job, now, "parsing", 1, 2)
            removed = pool.submit(remove)
            assert file_locked.wait(timeout=10)
            try:
                with pytest.raises(TimeoutError):
                    removed.result(timeout=0.5)
            finally:
                release_progress.set()
            assert removed.result(timeout=30).status_code == 200
            assert progress.result(timeout=30) is None
    finally:
        event.remove(engine, "after_cursor_execute", observe)
    assert admin.get(f"/api/admin/v1/imports/{batch_id}").json()["files"] == []
