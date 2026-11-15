from .content_helpers import key, process_jobs
from .test_imports import document
from .test_listening_imports import A, package, post, upload
from .test_multi_zip_imports import upload_zip


def test_scene_duplicates_and_reviewed_overwrite(admin):
    root = (
        "/api/admin/v1/imports/"
        + admin.post("/api/admin/v1/imports", json={"mode": "zip"}, headers=key()).json()["id"]
    )
    raw = document("同一份资料")
    upload_zip(admin, root.split("/")[-1], "两份.zip", [("a/内容.docx", raw), ("b/内容.docx", raw)])
    process_jobs(admin)
    details = admin.get(root + "/duplicates").json()
    assert details.get("total") == 1
    dupe = details["items"][0]
    assert (
        dupe["reason"] == "same_package"
        and dupe["target_kind"] == "scene_candidate"
        and dupe["target_available"]
    )
    rows = admin.get(root).json()["items"]
    selected = [{"id": r["id"], "revision": r["revision"]} for r in rows]
    body = {"items": selected, "content_type": "intensive", "overwrite": False}
    preview = admin.post(root + "/content-types/preview", json=body, headers=key()).json()
    assert preview["count"] == 1 and preview["items"][0]["pdf_conflict"]
    applied = admin.post(
        root + "/content-types/apply", json={**body, "version": preview["version"]}, headers=key()
    )
    assert applied.status_code == 200, applied.text
    assert [r["content_type"] for r in applied.json()["items"] if r["id"] == dupe["target_id"]] == [
        "intensive"
    ]
    assert (
        admin.post(
            root + "/content-types/apply",
            json={**body, "version": preview["version"]},
            headers=key(),
        ).status_code
        == 409
    )
    row = next(r for r in rows if r["id"] == dupe["candidate_id"])
    assert (
        admin.patch(
            root + "/items/" + row["id"],
            json={"content": row["content"], "revision": row["revision"], "selected": True},
            headers=key(),
        ).status_code
        == 409
    )


def test_listening_duplicate_detail_keeps_removed_target(admin):
    batch = upload(admin, post(admin, A + "/imports", {"mode": "zip"}), package(duplicate=True))
    route = A + "/imports/" + batch["id"]
    details = admin.get(route + "/duplicates?limit=1").json()
    assert details.get("total") == batch["counts"]["duplicate"] == 1
    item = details["items"][0]
    assert item["target_kind"] == "listening_candidate" and item["source_name"]
    post(
        admin,
        route + "/remove",
        {"revision": batch["revision"], "candidate_ids": [item["target_id"]]},
    )
    assert admin.get(route + "/duplicates").json()["items"][0]["target_available"] is False


def test_scene_removal_and_processing_failures_are_distinct_counts(admin):
    batch = admin.post("/api/admin/v1/imports", json={"mode": "zip"}, headers=key()).json()
    route = "/api/admin/v1/imports/" + batch["id"]
    upload_zip(admin, batch["id"], "删除练习.zip", [("a/内容.docx", document("保留文件"))])
    process_jobs(admin)
    first = admin.get(route).json()["items"][0]
    rows = admin.post(
        route + "/items/remove",
        headers=key(),
        json={"items": [{"id": first["id"], "revision": first["revision"]}]},
    ).json()
    assert rows.get("removed_count") == 1
    receipt = admin.get(route + "/confirmation").json()
    assert (
        receipt["removed"] == 1
        and receipt["failed"] == receipt["duplicates"] == receipt["unreadable"] == 0
    )


def test_legacy_source_hash_and_manual_draft_are_recognized_by_real_material(admin, system):
    from sqlalchemy import select

    from juya_api.import_models import ImportIdentity

    root = "/api/admin/v1/imports"
    raw = document("保留历史来源")

    def imported(label):
        bid = admin.post(root, json={"mode": "zip"}, headers=key()).json()["id"]
        upload_zip(admin, bid, label, [("资料/内容.docx", raw)])
        process_jobs(admin)
        return root + "/" + bid

    first = imported("首次.zip")
    item = admin.get(first).json()["items"][0]
    form = {"content": item["content"], "content_type": "illustrated"}
    manual = admin.post("/api/admin/v1/cards", headers=key(), json=form).json()
    dup = imported("同内容.zip")
    details = admin.get(dup + "/duplicates").json()["items"]
    assert (
        len(details) == 1
        and details[0]["target_kind"] == "scene_card"
        and details[0]["target_id"] == manual["id"]
    )
    admin.request(
        "DELETE",
        "/api/admin/v1/cards/" + manual["id"],
        headers=key(),
        json={"revision": manual["draft_revision"]},
    )
    assert not admin.get(dup + "/duplicates").json()["items"][0]["target_available"]
    review = admin.get(first + "/confirmation").json()
    admin.post(
        first + "/save", headers=key(), json={"confirmed": True, "version": review["version"]}
    )
    process_jobs(admin)
    with system["sessions"].begin() as db:
        identity = db.scalar(select(ImportIdentity))
        identity.content_hash = "a" * 64
    again = imported("旧摘要.zip")
    assert admin.get(again + "/duplicates").json()["total"] == 1


def test_listening_mixed_save_skips_duplicate_without_an_article_reference(admin):
    from .test_listening_imports import assign, topic

    category = topic(admin)
    batch = upload(admin, post(admin, A + "/imports", {"mode": "zip"}), package(duplicate=True))
    kept = next(c for c in batch["candidates"] if c["state"] != "duplicate")
    duplicate = next(c for c in batch["candidates"] if c["state"] == "duplicate")
    batch = assign(admin, batch, kept["id"], category["id"])
    route = A + "/imports/" + batch["id"]
    preview = admin.post(
        route + "/preview",
        headers=key(),
        json={"revision": batch["revision"], "candidate_ids": [duplicate["id"], kept["id"]]},
    )
    assert preview.status_code == 200, preview.text
    results = post(admin, route + "/save", {"preview_token": preview.json()["preview_token"]})[
        "items"
    ]
    assert results[0]["status"] == "skipped" and results[0]["article_id"] is None
    assert results[1]["status"] == "success"


def test_removal_gap_keeps_first_remaining_candidate_when_identical_material_is_appended(admin):
    admin.app.state.settings.import_card_limit = 2
    batch_id = admin.post("/api/admin/v1/imports", json={"mode": "zip"}, headers=key()).json()["id"]
    route = "/api/admin/v1/imports/" + batch_id
    material = document("乙")
    upload_zip(
        admin, batch_id, "原包.zip", [("a/资料.docx", document("甲")), ("b/资料.docx", material)]
    )
    process_jobs(admin)
    first, kept = admin.get(route).json()["items"]
    assert kept["content"]["name"] == "乙"
    removed = admin.post(
        route + "/items/remove",
        headers=key(),
        json={"items": [{"id": first["id"], "revision": first["revision"]}]},
    )
    assert removed.status_code == 200
    upload_zip(admin, batch_id, "后包.zip", [("另一个目录/资料.docx", material)])
    process_jobs(admin)
    rows = admin.get(route).json()["items"]
    detail = admin.get(route + "/duplicates").json()
    assert detail["total"] == 1
    assert detail["items"][0]["target_id"] == kept["id"]
    assert detail["items"][0]["reason"] == "cross_package"
    body = {
        "items": [{"id": r["id"], "revision": r["revision"]} for r in rows],
        "content_type": "illustrated",
    }
    assert [
        r["id"] for r in admin.post(route + "/content-types/preview", json=body).json()["items"]
    ] == [kept["id"]]
    review = admin.get(route + "/confirmation").json()
    assert review["count"] == review["duplicates"] == 1
    admin.post(
        route + "/save", headers=key(), json={"confirmed": True, "version": review["version"]}
    )
    process_jobs(admin)
    assert [r["state"] for r in admin.get(route).json()["items"]] == ["saved", "duplicate"]


def test_bulk_fill_leaves_unknown_and_multi_type_entries_for_individual_review(admin):
    from io import BytesIO

    from docx import Document

    batch_id = admin.post("/api/admin/v1/imports", json={"mode": "zip"}, headers=key()).json()["id"]
    route = "/api/admin/v1/imports/" + batch_id
    multi = Document(BytesIO(document("两个类型", content_type="图解词汇")))
    multi.paragraphs[2].insert_paragraph_before("内容类型：精读词汇")
    data = BytesIO()
    multi.save(data)
    upload_zip(
        admin,
        batch_id,
        "分类.zip",
        [
            ("a/资料.docx", document("缺字段")),
            ("b/资料.docx", document("陌生类型", content_type="自定义")),
            ("c/资料.docx", data.getvalue()),
        ],
    )
    process_jobs(admin)
    rows = admin.get(route).json()["items"]
    empty = next(row for row in rows if not row["type_raw"])
    selected = {
        "items": [{"id": r["id"], "revision": r["revision"]} for r in rows],
        "content_type": "illustrated",
        "overwrite": False,
    }
    preview = admin.post(route + "/content-types/preview", json=selected).json()
    assert [r["id"] for r in preview["items"]] == [empty["id"]]
    applied = admin.post(
        route + "/content-types/apply",
        json={**selected, "version": preview["version"]},
        headers=key(),
    ).json()["items"]
    for row in applied:
        if row["id"] != empty["id"]:
            assert row["content_type"] is None and any(
                i["code"] == "content_type_unknown" for i in row["issues"]
            )
            resolved = admin.patch(
                route + "/items/" + row["id"],
                json={
                    "selected": True,
                    "content": row["content"],
                    "revision": row["revision"],
                    "content_type": "illustrated",
                },
                headers=key(),
            ).json()
            assert resolved["type_origin"] == "manual" and resolved["type_raw"] == row["type_raw"]
            assert not any(i["code"] == "content_type_unknown" for i in resolved["issues"])


def test_explicit_patch_retains_file_origin_until_a_real_override(admin):
    batch_id = admin.post("/api/admin/v1/imports", json={"mode": "zip"}, headers=key()).json()["id"]
    route = "/api/admin/v1/imports/" + batch_id
    upload_zip(
        admin,
        batch_id,
        "原类型.zip",
        [("资料/内容.docx", document("稳定资料", content_type="图解词汇"))],
    )
    process_jobs(admin)
    row = admin.get(route).json()["items"][0]
    for content_type, expected in [
        ("illustrated", "file"),
        ("intensive", "override"),
        ("intensive", "override"),
    ]:
        row = admin.patch(
            route + "/items/" + row["id"],
            json={
                "selected": True,
                "content": row["content"],
                "revision": row["revision"],
                "content_type": content_type,
            },
            headers=key(),
        ).json()
        assert row["type_origin"] == expected and row["type_raw"] == ["图解词汇"]


def test_resumed_v2_unsaved_listening_source_matches_new_v3_upload(admin, system):
    from copy import deepcopy

    from juya_api.content_models import Media
    from juya_api.listening_models import ListeningCandidate
    from juya_api.listening_template import template_document
    from juya_api.security import fingerprint

    from .content_helpers import recording
    from .test_imports import archive

    material = archive([("one/content.docx", template_document()), ("one/full.wav", recording())])
    batch = upload(admin, post(admin, A + "/imports", {"mode": "zip"}), material)
    original = batch["candidates"][0]
    assert original["payload"]["vocabulary"][0]["source"]
    with system["sessions"].begin() as db:
        old = db.get(ListeningCandidate, original["id"])
        payload = deepcopy(old.payload)
        for word in payload["vocabulary"]:
            word.pop("source_reason", None)
        old.payload = payload
        canonical = deepcopy(payload)
        for field in ("image_id", "audio_id"):
            media = db.get(Media, payload[field]) if payload.get(field) else None
            canonical[field] = media.sha256 if media else None
        for word in canonical["vocabulary"]:
            word.pop("id")
            word.pop("source_hint")
            word["source"].pop("confirmed")
        old_hash = fingerprint({"canonical_version": 2, "payload": canonical})
        old.canonical_hash = old.source_hash = old_hash
    route = A + "/imports/" + batch["id"]
    recovered = admin.get(route).json()
    batch = upload(admin, recovered, material)
    assert batch["counts"]["duplicate"] == 1
    detail = admin.get(route + "/duplicates").json()["items"][0]
    assert detail["target_kind"] == "listening_candidate" and detail["target_id"] == original["id"]
    assert detail["reason"] == "cross_package" and detail["target_available"]
    with system["sessions"]() as db:
        old = db.get(ListeningCandidate, original["id"])
        assert old.canonical_hash == old.source_hash == old_hash and not old.article_id


def test_legacy_skipped_scene_receipt_survives_target_deletion_and_is_restored(admin, system):
    from juya_api.import_models import ImportItem
    from juya_api.import_service import content_hash
    from juya_api.job_models import Job

    batch_id = admin.post("/api/admin/v1/imports", json={"mode": "zip"}, headers=key()).json()["id"]
    route = "/api/admin/v1/imports/" + batch_id
    upload_zip(admin, batch_id, "旧包.zip", [("原目录/内容.docx", document("旧候选"))])
    process_jobs(admin)
    review = admin.get(route + "/confirmation").json()
    assert (
        admin.post(
            route + "/save", headers=key(), json={"confirmed": True, "version": review["version"]}
        ).status_code
        == 200
    )
    process_jobs(admin)
    item = admin.get(route).json()["items"][0]
    card_id = item["saved_card_id"]
    with system["sessions"].begin() as db:
        old = db.get(ImportItem, item["id"])
        assert old.duplicate_detail is None
        job = db.get(Job, old.job_id)
        assert job.state == "succeeded" and job.result["card_id"] == card_id
        job.result = {"card_id": card_id, "skipped": True}
        old.content = {
            **old.content,
            "vocabulary": [
                {k: v for k, v in word.items() if k not in {"source_hint", "source_reason"}}
                for word in old.content["vocabulary"]
            ],
        }
        old.last_saved_hash = content_hash(db, old.content, old.study_note)
    assert (
        admin.request(
            "DELETE",
            "/api/admin/v1/cards/" + card_id,
            headers=key(),
            json={"revision": item["saved_draft_revision"]},
        ).status_code
        == 200
    )
    assert admin.get(route + "/confirmation").json()["duplicates"] == 1
    restored = admin.get(route).json()["items"][0]
    assert restored["state"] == "duplicate"
    detail = admin.get(route + "/duplicates").json()["items"][0]
    assert (
        detail["target_id"] == card_id
        and detail["source_name"] == "旧包.zip"
        and not detail["target_available"]
    )
    assert admin.get(route + "/confirmation").json()["count"] == 0
    with system["sessions"]() as db:
        assert db.get(ImportItem, item["id"]).duplicate_detail["target_id"] == card_id
