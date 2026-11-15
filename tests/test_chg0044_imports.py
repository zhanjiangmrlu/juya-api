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
