"""Multiple archives share a review batch without sharing source identity or media."""

from .content_helpers import key, picture, process_jobs, recording
from .test_imports import archive, document


def upload_zip(admin, batch_id, name, entries):
    response = admin.post(
        f"/api/admin/v1/imports/{batch_id}/files?kind=zip",
        headers=key(),
        files={"file": (name, archive(entries), "application/zip")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_three_archives_keep_same_paths_separate_and_report_every_source(admin):
    batch_id = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()["id"]
    roots = []
    for name in ["第一包.zip", "第二包.zip", "第三包.zip"]:
        roots.append(
            upload_zip(
                admin,
                batch_id,
                name,
                [
                    ("外层/同名文件夹/内容.docx", document(name)),
                    ("外层/同名文件夹/场景图.png", picture()),
                    ("外层/同名文件夹/完整音频.wav", recording()),
                ],
            )
        )
    process_jobs(admin)
    result = admin.get(f"/api/admin/v1/imports/{batch_id}").json()
    assert len(result["items"]) == 3
    assert {i["source_zip_name"] for i in result["items"]} == {
        "第一包.zip",
        "第二包.zip",
        "第三包.zip",
    }
    assert {i["source_folder"] for i in result["items"]} == {"外层/同名文件夹"}
    for item in result["items"]:
        parent = next(root for root in roots if root["id"] == item["source_zip_id"])
        assert item["source_zip_name"] == parent["name"]
        for field in ["image_id", "audio_id"]:
            medium = next(f for f in result["files"] if f["media_id"] == item["content"][field])
            assert medium["parent_id"] == parent["id"]
    confirmation = admin.get(f"/api/admin/v1/imports/{batch_id}/confirmation").json()
    assert confirmation["count"] == 3
    assert (
        admin.post(
            f"/api/admin/v1/imports/{batch_id}/save",
            headers=key(),
            json={"confirmed": True, "version": confirmation["version"]},
        ).status_code
        == 200
    )
    process_jobs(admin)
    assert admin.get("/api/admin/v1/cards").json()["total"] == 3


def test_one_archive_three_folders_reports_real_persistent_progress(admin):
    batch_id = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()["id"]
    root = upload_zip(
        admin,
        batch_id,
        "三张.zip",
        [(f"资料/场景{number}/内容.docx", document(f"卡片{number}")) for number in range(3)],
    )
    process_jobs(admin)
    result = admin.get(f"/api/admin/v1/imports/{batch_id}").json()
    assert len(result["items"]) == 3
    source = next(f for f in result["files"] if f["id"] == root["id"])
    assert source["progress"] == {"phase": "parsed", "processed": 3, "total": 3}
    assert all(i["state"] == "incomplete" for i in result["items"])


def test_zip_staging_rejects_other_archive_or_folder_media(admin):
    batch_id = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()["id"]
    for name, folders in [("one.zip", ["one", "two"]), ("two.zip", ["one"])]:
        upload_zip(
            admin,
            batch_id,
            name,
            [
                entry
                for folder in folders
                for entry in [
                    (f"{folder}/内容.docx", document(name + folder)),
                    (f"{folder}/场景图.png", picture()),
                ]
            ],
        )
    process_jobs(admin)
    items = admin.get(f"/api/admin/v1/imports/{batch_id}").json()["items"]
    first = items[0]
    for other in items[1:]:
        response = admin.patch(
            f"/api/admin/v1/imports/{batch_id}/items/{first['id']}",
            headers=key(),
            json={
                "revision": first["revision"],
                "selected": True,
                "content": dict(first["content"], image_id=other["content"]["image_id"]),
            },
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "import_media_source"


def test_same_incomplete_object_is_skipped_after_renamed_zip_reimport(admin):
    raw = document("只有内容也能留草稿")
    for index in range(2):
        batch_id = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()[
            "id"
        ]
        upload_zip(admin, batch_id, f"重命名{index}.zip", [("场景/内容.docx", raw)])
        process_jobs(admin)
        confirmation = admin.get(f"/api/admin/v1/imports/{batch_id}/confirmation").json()
        if index == 0:
            assert confirmation["incomplete"] == 1
            admin.post(
                f"/api/admin/v1/imports/{batch_id}/save",
                headers=key(),
                json={"confirmed": True, "version": confirmation["version"]},
            )
            process_jobs(admin)
        else:
            assert confirmation["count"] == 0
            assert confirmation["duplicates"] == 1
    assert admin.get("/api/admin/v1/cards").json()["total"] == 1


def test_identical_zip_with_a_different_name_reuses_batch_file(admin):
    batch_id = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()["id"]
    entries = [("场景/内容.docx", document("一次接收"))]
    # 同一文件重命名必须重传同一字节，重建ZIP会因时间戳改变文件哈希
    raw = archive(entries)
    results = [
        admin.post(
            f"/api/admin/v1/imports/{batch_id}/files?kind=zip",
            headers=key(),
            files={"file": (name, raw, "application/zip")},
        )
        for name in ["one.zip", "renamed.zip"]
    ]
    assert all(response.status_code == 201 for response in results)
    first, second = [response.json() for response in results]
    assert second["id"] == first["id"]
    process_jobs(admin)
    assert len(admin.get(f"/api/admin/v1/imports/{batch_id}").json()["items"]) == 1


def test_appending_unparsed_zip_invalidates_previous_confirmation(admin):
    batch_id = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()["id"]
    upload_zip(admin, batch_id, "one.zip", [("one/内容.docx", document("第一张"))])
    process_jobs(admin)
    confirmation = admin.get(f"/api/admin/v1/imports/{batch_id}/confirmation").json()
    upload_zip(admin, batch_id, "two.zip", [("two/内容.docx", document("第二张"))])
    response = admin.post(
        f"/api/admin/v1/imports/{batch_id}/save",
        headers=key(),
        json={"confirmed": True, "version": confirmation["version"]},
    )
    assert response.status_code == 409, response.text
    assert admin.get("/api/admin/v1/cards").json()["total"] == 0


def test_scoped_retry_saves_failed_card_without_saving_newly_added_items(admin, system):
    from juya_api.job_models import Job

    batch_id = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()["id"]
    upload_zip(admin, batch_id, "one.zip", [("one/内容.docx", document("需要重试"))])
    process_jobs(admin)
    confirmation = admin.get(f"/api/admin/v1/imports/{batch_id}/confirmation").json()
    admin.post(
        f"/api/admin/v1/imports/{batch_id}/save",
        headers=key(),
        json={"confirmed": True, "version": confirmation["version"]},
    )
    item = admin.get(f"/api/admin/v1/imports/{batch_id}").json()["items"][0]
    with system["sessions"].begin() as db:
        job = db.get(Job, item["job_id"])
        job.state, job.error_code = "failed", "worker_interrupted"
    upload_zip(admin, batch_id, "two.zip", [("two/内容.docx", document("稍后再保存"))])
    process_jobs(admin)
    confirmation = admin.get(
        f"/api/admin/v1/imports/{batch_id}/confirmation", params={"item_ids": item["id"]}
    ).json()
    assert confirmation["count"] == 1
    response = admin.post(
        f"/api/admin/v1/imports/{batch_id}/save",
        headers=key(),
        json={"confirmed": True, "version": confirmation["version"], "item_ids": [item["id"]]},
    )
    assert response.status_code == 200, response.text
    process_jobs(admin)
    listing = admin.get("/api/admin/v1/cards").json()
    assert listing["total"] == 1
    assert listing["items"][0]["content"]["name"] == "需要重试"


def test_two_identical_objects_in_one_batch_report_the_second_as_skipped(admin):
    batch_id = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()["id"]
    raw = document("相同的不完整对象")
    for index in range(2):
        upload_zip(admin, batch_id, f"资料{index}.zip", [(f"场景{index}/内容.docx", raw)])
    process_jobs(admin)
    confirmation = admin.get(f"/api/admin/v1/imports/{batch_id}/confirmation").json()
    admin.post(
        f"/api/admin/v1/imports/{batch_id}/save",
        headers=key(),
        json={"confirmed": True, "version": confirmation["version"]},
    )
    process_jobs(admin)
    result = admin.get(f"/api/admin/v1/imports/{batch_id}").json()
    assert sorted(item["state"] for item in result["items"]) == ["duplicate", "saved"]
    assert admin.get("/api/admin/v1/cards").json()["total"] == 1


def test_old_lease_cannot_overwrite_import_progress(admin, system):
    from datetime import timedelta

    import pytest

    from juya_api.database import naive_utc
    from juya_api.errors import DomainError
    from juya_api.import_service import parse_progress
    from juya_api.job_models import Job

    batch_id = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()["id"]
    root = upload_zip(admin, batch_id, "进度.zip", [("场景/内容.docx", document("进度"))])
    now = naive_utc(system["time"][0])
    job = {"id": root["job_id"], "lease": "old", "payload": {"file_id": root["id"]}}
    with system["sessions"].begin() as db:
        row = db.get(Job, root["job_id"])
        row.state, row.lease, row.lease_expires_at = "running", "new", now + timedelta(minutes=5)
    with pytest.raises(DomainError):
        parse_progress(system["sessions"], job, now, "parsing", 9, 9)
    job["lease"] = "new"
    parse_progress(system["sessions"], job, now, "parsing", 1, 3)
    progress = admin.get(f"/api/admin/v1/imports/{batch_id}").json()["files"][0]["progress"]
    assert progress == {"phase": "parsing", "processed": 1, "total": 3}


def test_new_audio_capable_apis_require_additive_playback_migration(system):
    from sqlalchemy import text

    from juya_api.content_models import SettingCounter

    with system["sessions"].begin() as db:
        db.execute(text("DROP TABLE IF EXISTS alembic_version"))
        db.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        db.execute(text("INSERT INTO alembic_version VALUES ('0010')"))
        db.merge(SettingCounter(name="schema_contract", value=1))
    assert system["admin"].get("/health/ready").status_code == 503
    assert system["mini"].get("/health/ready").status_code == 503


def test_docx_mode_preserves_conflicting_file_kind_rejection(admin):
    batch_id = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "docx"}).json()[
        "id"
    ]
    raw = document("保留原有文件类型核对")
    path = f"/api/admin/v1/imports/{batch_id}/files"
    first = admin.post(path + "?kind=docx", headers=key(), files={"file": ("内容.docx", raw)})
    assert first.status_code == 201
    conflicting = admin.post(
        path + "?kind=image", headers=key(), files={"file": ("内容.docx", raw)}
    )
    assert conflicting.status_code == 409, conflicting.text
    assert conflicting.json()["error"]["code"] == "import_file_kind"


def test_legacy_incomplete_identity_survives_unsaved_staging_media_changes(admin, system):
    from juya_api.import_models import ImportIdentity, ImportItem
    from juya_api.import_service import object_key
    from juya_api.security import fingerprint

    raw = document("历史不完整草稿")
    batch_id = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()["id"]
    upload_zip(admin, batch_id, "old.zip", [("场景/内容.docx", raw)])
    process_jobs(admin)
    confirmation = admin.get(f"/api/admin/v1/imports/{batch_id}/confirmation").json()
    admin.post(
        f"/api/admin/v1/imports/{batch_id}/save",
        headers=key(),
        json={"confirmed": True, "version": confirmation["version"]},
    )
    process_jobs(admin)
    item = admin.get(f"/api/admin/v1/imports/{batch_id}").json()["items"][0]
    with system["sessions"].begin() as db:
        identity = db.get(ImportIdentity, object_key(db, db.get(ImportItem, item["id"])))
        legacy = ImportIdentity(
            object_key=fingerprint({"incomplete_item": item["id"]}),
            card_id=identity.card_id,
            content_hash=identity.content_hash,
            draft_revision=identity.draft_revision,
        )
        db.delete(identity)
        db.add(legacy)
    medium = admin.post(
        "/api/admin/v1/media?kind=image",
        headers=key(),
        files={"file": ("补图.png", picture(), "image/png")},
    ).json()
    process_jobs(admin)
    changed = admin.patch(
        f"/api/admin/v1/imports/{batch_id}/items/{item['id']}",
        headers=key(),
        json={
            "revision": item["revision"],
            "selected": True,
            "content": dict(item["content"], image_id=medium["id"]),
        },
    )
    assert changed.status_code == 200
    second = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()["id"]
    upload_zip(admin, second, "renamed.zip", [("场景/内容.docx", raw)])
    process_jobs(admin)
    confirmation = admin.get(f"/api/admin/v1/imports/{second}/confirmation").json()
    assert confirmation["duplicates"] == 1
    assert confirmation["count"] == 0


def test_media_completion_invalidates_confirmation_without_a_staging_edit(admin, system):
    from juya_api.worker import run_job

    batch_id = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()["id"]
    root = upload_zip(
        admin,
        batch_id,
        "素材异步.zip",
        [
            ("场景/内容.docx", document("读取期间的保存确认")),
            ("场景/场景图.png", picture()),
            ("场景/完整音频.wav", recording()),
        ],
    )
    app = system["admin"].app
    run_job(app.state.settings, app.state.sessions, root["job_id"], clock=app.state.clock)
    confirmation = admin.get(f"/api/admin/v1/imports/{batch_id}/confirmation").json()
    process_jobs(admin)
    response = admin.post(
        f"/api/admin/v1/imports/{batch_id}/save",
        headers=key(),
        json={"confirmed": True, "version": confirmation["version"]},
    )
    assert response.status_code == 409
