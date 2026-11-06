"""PDF publication identity, controlled delivery and SQL-filtered note discovery."""

import io

import pytest

from .content_helpers import content, draft, key, process_jobs, publish


def pdf(label="notes"):
    # A small, independently encoded real PDF, including a readable content stream.
    stream = f"BT /F1 12 Tf 10 10 Td ({label}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    output = io.BytesIO(b"%PDF-1.4\n")
    output.seek(0, 2)
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(output.tell())
        output.write(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = output.tell()
    output.write(b"xref\n0 5\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.write(f"{offset:010} 00000 n \n".encode())
    output.write(f"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return output.getvalue()


def upload(admin, data=None):
    result = admin.post(
        "/api/admin/v1/media?kind=study_note",
        headers=key(),
        files={"file": ("学习笔记.pdf", pdf() if data is None else data, "application/pdf")},
    )
    assert result.status_code == 201, result.text
    return result.json()


def save_note(admin, card, change):
    result = admin.put(
        f"/api/admin/v1/cards/{card['id']}",
        headers=key(),
        json={"revision": card["draft_revision"], "content": card["content"], "study_note": change},
    )
    assert result.status_code == 200, result.text
    return result.json()


def ticket(mini, card, note):
    result = mini.get(
        f"/api/mini/v1/cards/{card['id']}/media/{note['media_id']}/url",
        params={"purpose": "study_note", "study_note_version_id": note["version_id"]},
    )
    assert result.status_code == 200, result.text
    return result.json()["url"]


def test_note_only_publication_keeps_content_order_progress_and_expires_old_ticket(
    admin, mini, system
):
    card = publish(admin, draft(admin))
    old_version, old_order = card["current_version_id"], card["sort_order"]
    mini.get(f"/api/mini/v1/cards/{card['id']}")
    assert (
        mini.post(
            f"/api/mini/v1/cards/{card['id']}/complete",
            headers=key(),
            json={"version_id": old_version},
        ).status_code
        == 200
    )
    before = mini.get("/api/mini/v1/me/statistics").json()
    medium = upload(admin)
    assert medium["state"] == "processing"
    pending = save_note(admin, card, {"action": "set", "media_id": medium["id"]})
    assert pending["study_note"]["can_publish"] is False
    assert mini.get("/api/mini/v1/cards?scope=published&has_study_note=true").json()["total"] == 0
    process_jobs(admin)
    card = publish(admin, pending)
    assert (card["current_version_id"], card["sort_order"]) == (old_version, old_order)
    detail = mini.get(f"/api/mini/v1/cards/{card['id']}?mark_started=false").json()
    note = detail["study_note"]
    assert note["filename"] == "学习笔记.pdf" and note["size"] == len(pdf())
    url = ticket(mini, card, note)
    assert mini.get(url).content == pdf()
    assert mini.head(url).status_code == 200
    assert mini.get(url, headers={"Range": "bytes=0-3"}).content == b"%PDF"
    assert mini.get("/api/mini/v1/me/statistics").json() == before
    listed = mini.get("/api/mini/v1/cards?scope=published&has_study_note=true").json()
    assert listed["total"] == 1 and listed["items"][0]["state"]["completed"]
    assert "media_id" not in listed["items"][0] and "study_note" not in listed["items"][0]
    removed = save_note(admin, card, {"action": "remove"})
    assert mini.get(url).status_code == 200
    publish(admin, removed)
    assert mini.get(url).status_code == 409
    assert mini.head(url).status_code == 409
    assert mini.get("/api/mini/v1/cards?scope=published&has_study_note=true").json()["total"] == 0


@pytest.mark.parametrize(
    "bad,expected_code",
    [
        (b"not a pdf", "study_note_format_invalid"),
        (b"%PDF-1.4\ntruncated", "study_note_invalid"),
        (b"%PDF-1.4\n%%EOF", "study_note_invalid"),
    ],
)
def test_failed_pdf_replacement_preserves_effective_note_and_blocks_publish(
    admin, mini, bad, expected_code
):
    medium = upload(admin)
    process_jobs(admin)
    card = publish(
        admin, save_note(admin, draft(admin), {"action": "set", "media_id": medium["id"]})
    )
    old = card["published_study_note"]
    broken = upload(admin, bad)
    process_jobs(admin)
    result = admin.get(f"/api/admin/v1/media/{broken['id']}/status").json()
    assert result["state"] == "failed" and result["error_code"] == expected_code
    candidate = save_note(admin, card, {"action": "set", "media_id": broken["id"]})
    assert candidate["study_note"]["attachment"]["id"] == medium["id"]
    preview = admin.post(
        f"/api/admin/v1/cards/{card['id']}/preview",
        headers=key(),
        json={"revision": candidate["draft_revision"]},
    )
    assert preview.status_code == 422
    assert (
        mini.get(f"/api/mini/v1/cards/{card['id']}?mark_started=false").json()["study_note"] == old
    )
    restored = save_note(admin, candidate, {"action": "keep"})
    assert restored["study_note"]["can_publish"]


def test_notes_filter_runs_before_pagination_and_notes_queue_keeps_completed(admin, mini):
    base = content(admin)
    cards = [publish(admin, draft(admin, dict(base, name=f"卡片{i}"))) for i in range(4)]
    medium = upload(admin)
    process_jobs(admin)
    cards[0] = publish(
        admin, save_note(admin, cards[0], {"action": "set", "media_id": medium["id"]})
    )
    first = mini.get(
        "/api/mini/v1/cards?scope=published&has_study_note=true&limit=1&page=99"
    ).json()
    assert first["total"] == 1 and first["page"] == 1
    assert first["items"][0]["id"] == cards[0]["id"] and first["items"][0]["has_study_note"]
    mini.post(
        f"/api/mini/v1/cards/{cards[0]['id']}/complete",
        headers=key(),
        json={"version_id": cards[0]["current_version_id"]},
    )
    queued = mini.post(
        "/api/mini/v1/learning-queues",
        headers=key(),
        json={"source": "learning_notes", "card_id": cards[0]["id"]},
    )
    assert queued.status_code == 201, queued.text
    path = "/api/mini/v1/learning-queues/" + queued.json()["id"]
    assert mini.get(path).json()["items"][0]["available"]
    cards[0] = publish(admin, save_note(admin, cards[0], {"action": "remove"}))
    assert not mini.get(path).json()["items"][0]["available"]
    assert mini.get(path).json()["end_reason"] == "round_complete"


def test_zip_notes_are_isolated_and_unresolved_candidates_save_but_do_not_publish(admin):
    from .content_helpers import picture, recording
    from .test_imports import archive, document

    batch = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()["id"]
    for name, notes in [
        ("one.zip", [("a.pdf", pdf("a")), ("b.pdf", pdf("b"))]),
        ("two.zip", [("a.pdf", pdf("c"))]),
    ]:
        entries = [
            ("same/内容.docx", document(name)),
            ("same/场景图.png", picture()),
            ("same/完整音频.wav", recording()),
        ]
        entries += [("same/" + filename, body) for filename, body in notes]
        response = admin.post(
            f"/api/admin/v1/imports/{batch}/files?kind=zip",
            headers=key(),
            files={"file": (name, archive(entries), "application/zip")},
        )
        assert response.status_code == 201
    process_jobs(admin)
    items = admin.get(f"/api/admin/v1/imports/{batch}").json()["items"]
    multi = next(item for item in items if item["source_zip_name"] == "one.zip")
    single = next(item for item in items if item["source_zip_name"] == "two.zip")
    assert multi["study_note"]["action"] == "unresolved"
    assert len(multi["study_note"]["candidates"]) == 2
    assert single["study_note"]["attachment"]["state"] == "ready"
    wrong = admin.patch(
        f"/api/admin/v1/imports/{batch}/items/{multi['id']}",
        headers=key(),
        json={
            "revision": multi["revision"],
            "content": multi["content"],
            "selected": True,
            "study_note": {"action": "set", "media_id": single["study_note"]["attachment"]["id"]},
        },
    )
    assert wrong.status_code == 422
    review = admin.get(f"/api/admin/v1/imports/{batch}/confirmation").json()
    response = admin.post(
        f"/api/admin/v1/imports/{batch}/save",
        headers=key(),
        json={"confirmed": True, "version": review["version"]},
    )
    assert response.status_code == 200, response.text
    process_jobs(admin)
    items = admin.get(f"/api/admin/v1/imports/{batch}").json()["items"]
    assert all(item["state"] == "saved" for item in items)
    multi = next(item for item in items if item["source_zip_name"] == "one.zip")
    card = admin.get(f"/api/admin/v1/cards/{multi['saved_card_id']}").json()
    assert card["study_note"]["action"] == "unresolved" and not card["study_note"]["can_publish"]
    response = admin.post(
        f"/api/admin/v1/cards/{card['id']}/preview",
        headers=key(),
        json={"revision": card["draft_revision"]},
    )
    assert response.status_code == 422


def test_old_zip_update_omission_preserves_pdf_and_explicit_remove_changes_deduplication(admin):
    from .test_imports import archive, document

    medium = upload(admin)
    process_jobs(admin)
    card = publish(
        admin, save_note(admin, draft(admin), {"action": "set", "media_id": medium["id"]})
    )
    original = card["published_study_note"]
    batch = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()["id"]
    admin.post(
        f"/api/admin/v1/imports/{batch}/files?kind=zip",
        headers=key(),
        files={
            "file": (
                "old.zip",
                archive([("card/内容.docx", document("旧包更新"))]),
                "application/zip",
            )
        },
    )
    process_jobs(admin)
    item = admin.get(f"/api/admin/v1/imports/{batch}").json()["items"][0]
    staged = admin.patch(
        f"/api/admin/v1/imports/{batch}/items/{item['id']}",
        headers=key(),
        json={
            "revision": item["revision"],
            "content": card["content"],
            "selected": True,
            "target_card_id": card["id"],
            "target_revision": card["draft_revision"],
            "update_confirmed": True,
        },
    )
    assert staged.status_code == 200, staged.text
    review = admin.get(f"/api/admin/v1/imports/{batch}/confirmation").json()
    admin.post(
        f"/api/admin/v1/imports/{batch}/save",
        headers=key(),
        json={"confirmed": True, "version": review["version"]},
    )
    process_jobs(admin)
    updated = admin.get(f"/api/admin/v1/cards/{card['id']}").json()
    assert updated["study_note"]["attachment"]["id"] == medium["id"]
    assert updated["published_study_note"] == original
    item = admin.get(f"/api/admin/v1/imports/{batch}").json()["items"][0]
    remove = admin.patch(
        f"/api/admin/v1/imports/{batch}/items/{item['id']}",
        headers=key(),
        json={
            "revision": item["revision"],
            "content": updated["content"],
            "selected": True,
            "target_card_id": card["id"],
            "target_revision": updated["draft_revision"],
            "update_confirmed": True,
            "study_note": {"action": "remove"},
        },
    )
    assert remove.status_code == 200, remove.text
    review = admin.get(f"/api/admin/v1/imports/{batch}/confirmation").json()
    assert review["count"] == 1
    admin.post(
        f"/api/admin/v1/imports/{batch}/save",
        headers=key(),
        json={"confirmed": True, "version": review["version"]},
    )
    process_jobs(admin)
    updated = admin.get(f"/api/admin/v1/cards/{card['id']}").json()
    assert updated["study_note"]["action"] == "remove"
    assert updated["published_study_note"] == original
    assert publish(admin, updated)["published_study_note"] is None


def test_cancel_failed_replacement_restores_valid_unpublished_attachment(admin):
    valid = upload(admin)
    process_jobs(admin)
    card = save_note(admin, draft(admin), {"action": "set", "media_id": valid["id"]})
    broken = upload(admin, b"broken")
    process_jobs(admin)
    failed = save_note(admin, card, {"action": "set", "media_id": broken["id"]})
    assert failed["study_note"]["attachment"]["id"] == valid["id"]
    cancelled = save_note(admin, failed, {"action": "keep"})
    assert cancelled["study_note"]["attachment"]["id"] == valid["id"]
    assert cancelled["study_note"]["pending_attachment"] is None
    assert cancelled["study_note"]["can_publish"]


@pytest.mark.parametrize("change", ["free_closed", "revoke", "offline", "delete", "session"])
def test_study_note_ticket_rechecks_current_permission_for_all_http_methods(
    admin, mini, system, change
):
    from juya_api.models import MiniSession

    from .test_learning_access import change as authorize
    from .test_learning_access import user_id

    medium = upload(admin)
    process_jobs(admin)
    card = publish(
        admin, save_note(admin, draft(admin), {"action": "set", "media_id": medium["id"]})
    )
    if change == "revoke":
        authorize(admin, user_id(mini), "grant")
        path = f"/api/admin/v1/cards/{card['id']}/free-access"
        current = admin.get(path).json()
        admin.put(path, headers=key(), json={"is_free": False, "revision": current["revision"]})
    note = mini.get(f"/api/mini/v1/cards/{card['id']}?mark_started=false").json()["study_note"]
    url = ticket(mini, card, note)
    if change in {"free_closed", "revoke"}:
        if change == "revoke":
            authorize(admin, user_id(mini), "revoke")
        else:
            path = f"/api/admin/v1/cards/{card['id']}/free-access"
            current = admin.get(path).json()
            admin.put(path, headers=key(), json={"is_free": False, "revision": current["revision"]})
        expected = 403
        listed = mini.get("/api/mini/v1/cards?scope=published&has_study_note=true").json()["items"][
            0
        ]
        assert listed["has_study_note"] and not listed["access"]["can_learn"]
        assert "学习笔记.pdf" not in str(listed) and "media_id" not in listed
    elif change == "session":
        from sqlalchemy import delete

        with system["sessions"].begin() as db:
            db.execute(delete(MiniSession))
        expected = 401
    else:
        path = f"/api/admin/v1/cards/{card['id']}" + ("/offline" if change == "offline" else "")
        result = admin.request(
            "POST" if change == "offline" else "DELETE",
            path,
            headers=key(),
            json={"revision": card["draft_revision"]},
        )
        assert result.status_code == 200
        expected = 410
    assert mini.get(url).status_code == expected
    assert mini.head(url).status_code == expected
    assert mini.get(url, headers={"Range": "bytes=0-3"}).status_code == expected


def test_notes_download_and_admin_preview_do_not_start_or_complete_learning(admin, mini, system):
    from sqlalchemy import func, select

    from juya_api.discovery_models import ReadingStart
    from juya_api.learning_models import Completion, DailyLearning

    medium = upload(admin)
    process_jobs(admin)
    card = publish(
        admin, save_note(admin, draft(admin), {"action": "set", "media_id": medium["id"]})
    )
    stats = mini.get("/api/mini/v1/me/statistics").json()
    assert stats["completed_cards"] == 0
    detail = mini.get(f"/api/mini/v1/cards/{card['id']}?mark_started=false").json()
    assert mini.get(ticket(mini, card, detail["study_note"])).status_code == 200
    assert admin.get(f"/api/admin/v1/media/{medium['id']}").status_code == 200
    assert admin.get(f"/api/admin/v1/cards/{card['id']}/published").status_code == 200
    with system["sessions"]() as db:
        for model in [ReadingStart, Completion, DailyLearning]:
            assert db.scalar(select(func.count()).select_from(model)) == 0
    assert mini.get("/api/mini/v1/me/statistics").json() == stats


def test_publication_transaction_rolls_back_both_note_and_body_on_failure(admin, mini, monkeypatch):
    from juya_api import content_service
    from juya_api.errors import DomainError

    medium = upload(admin)
    process_jobs(admin)
    card = publish(admin, draft(admin))
    candidate = save_note(admin, card, {"action": "set", "media_id": medium["id"]})
    preview = admin.post(
        f"/api/admin/v1/cards/{card['id']}/preview",
        headers=key(),
        json={"revision": candidate["draft_revision"]},
    ).json()
    original = content_service.publish_note

    def fail_after_switch(db, row, draft, now):
        original(db, row, draft, now)
        raise DomainError(503, "simulated_write_failure", "模拟发布事务失败")

    monkeypatch.setattr(content_service, "publish_note", fail_after_switch)
    failed = admin.post(
        f"/api/admin/v1/cards/{card['id']}/publish",
        headers=key(),
        json={"revision": candidate["draft_revision"], "preview_id": preview["preview_id"]},
    )
    assert failed.status_code == 503
    current = mini.get(f"/api/mini/v1/cards/{card['id']}?mark_started=false").json()
    assert current["version_id"] == card["current_version_id"] and current["study_note"] is None
    assert admin.get(f"/api/admin/v1/cards/{card['id']}").json()["study_note"]["action"] == "set"


def test_zip_example_includes_optional_pdf_and_instructions(admin):
    import zipfile

    package = admin.get("/api/admin/v1/imports/example")
    assert package.status_code == 200
    with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
        assert "在咖啡店点单/学习笔记.pdf" in archive.namelist()
        assert archive.read("在咖啡店点单/学习笔记.pdf").startswith(b"%PDF-")
        instructions = archive.read("填写说明.txt").decode()
        assert "PDF选填" in instructions and "每卡最多一份" in instructions


def test_pdf_validation_rejects_encryption_and_exposes_actual_limit(admin, system):
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(pdf())))
    writer.encrypt("secret-test-password")
    data = io.BytesIO()
    writer.write(data)
    medium = upload(admin, data.getvalue())
    process_jobs(admin)
    assert (
        admin.get(f"/api/admin/v1/media/{medium['id']}/status").json()["error_code"]
        == "study_note_encrypted"
    )
    system["settings"].study_note_limit_mb = 1
    assert (
        admin.get("/api/admin/v1/media/configuration").json()["study_note_limit_bytes"] == 1048576
    )
    for body in [b"", b"x" * (1048576 + 1)]:
        result = admin.post(
            "/api/admin/v1/media?kind=study_note",
            headers=key(),
            files={"file": ("bad.pdf", body, "application/pdf")},
        )
        assert result.status_code == 413


@pytest.mark.mysql
def test_mysql_note_publication_replays_one_version_and_rejects_stale_saves(admin, system):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from sqlalchemy import func, select

    from juya_api.content_models import CardStudyNoteVersion

    if system["engine"].dialect.name != "mysql":
        pytest.skip("Dedicated local MySQL required")
    medium = upload(admin)
    process_jobs(admin)
    card = save_note(admin, draft(admin), {"action": "set", "media_id": medium["id"]})
    preview = admin.post(
        f"/api/admin/v1/cards/{card['id']}/preview",
        headers=key(),
        json={"revision": card["draft_revision"]},
    ).json()
    headers, barrier = key(), Barrier(2)

    def confirm():
        barrier.wait(5)
        return admin.post(
            f"/api/admin/v1/cards/{card['id']}/publish",
            headers=headers,
            json={"revision": card["draft_revision"], "preview_id": preview["preview_id"]},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(confirm) for _ in range(2)]
        responses = [future.result(timeout=20) for future in futures]
    assert [r.status_code for r in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()
    with system["sessions"]() as db:
        assert db.scalar(select(func.count()).select_from(CardStudyNoteVersion)) == 1
    barrier = Barrier(2)

    def save(action):
        barrier.wait(5)
        return admin.put(
            f"/api/admin/v1/cards/{card['id']}",
            headers=key(),
            json={
                "revision": card["draft_revision"],
                "content": card["content"],
                "study_note": {"action": action},
            },
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(save, "remove"), pool.submit(save, "keep")
        assert sorted([a.result(timeout=20).status_code, b.result(timeout=20).status_code]) == [
            200,
            409,
        ]


def test_replacement_uses_new_note_version_and_old_download_cannot_open_new_pdf(admin, mini):
    one = upload(admin)
    process_jobs(admin)
    card = publish(admin, save_note(admin, draft(admin), {"action": "set", "media_id": one["id"]}))
    original = card["published_study_note"]
    old = ticket(mini, card, original)
    two = upload(admin, pdf("replacement"))
    process_jobs(admin)
    candidate = save_note(admin, card, {"action": "set", "media_id": two["id"]})
    assert mini.get(old).content == pdf()
    new_card = publish(admin, candidate)
    current = new_card["published_study_note"]
    assert current["version_id"] != original["version_id"]
    assert new_card["current_version_id"] == card["current_version_id"]
    assert mini.get(old).status_code == 409
    assert mini.get(ticket(mini, new_card, current)).content == pdf("replacement")


def test_unresolved_selection_keeps_original_editor_pdf_until_explicit_removal(admin):
    medium = upload(admin)
    process_jobs(admin)
    card = publish(
        admin, save_note(admin, draft(admin), {"action": "set", "media_id": medium["id"]})
    )
    unresolved = save_note(admin, card, {"action": "unresolved"})
    assert unresolved["study_note"]["attachment"]["id"] == medium["id"]
    assert not unresolved["study_note"]["can_publish"]
    cancelled = save_note(admin, unresolved, {"action": "keep"})
    assert cancelled["study_note"]["attachment"]["id"] == medium["id"]


def test_zip_pdf_candidate_is_recognized_by_format_extension_without_title_guessing():
    from juya_api.import_service import asset_kind

    assert asset_kind("card/词汇学习笔记.pdf") == "study_note"
    assert asset_kind("card/单词资料.PDF") == "study_note"
    assert asset_kind("card/词汇音频.mp3") == "unused"


def test_cancel_pending_replacement_rejects_late_validation_binding(admin):
    original = upload(admin)
    process_jobs(admin)
    card = publish(
        admin, save_note(admin, draft(admin), {"action": "set", "media_id": original["id"]})
    )
    replacement = upload(admin, pdf("late-ready"))
    pending = save_note(admin, card, {"action": "set", "media_id": replacement["id"]})
    process_jobs(admin)
    cancelled = save_note(admin, pending, {"action": "keep"})
    assert cancelled["study_note"]["attachment"]["id"] == original["id"]
    assert publish(admin, cancelled)["published_study_note"]["media_id"] == original["id"]


def import_package(admin, name, entries):
    from .test_imports import archive

    batch = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()["id"]
    result = admin.post(
        f"/api/admin/v1/imports/{batch}/files?kind=zip",
        headers=key(),
        files={"file": (name, archive(entries), "application/zip")},
    )
    assert result.status_code == 201, result.text
    process_jobs(admin)
    return batch, admin.get(f"/api/admin/v1/imports/{batch}").json()["items"][0]


def save_import(admin, batch):
    confirmation = admin.get(f"/api/admin/v1/imports/{batch}/confirmation").json()
    result = admin.post(
        f"/api/admin/v1/imports/{batch}/save",
        headers=key(),
        json={"confirmed": True, "version": confirmation["version"]},
    )
    assert result.status_code == 200, result.text
    process_jobs(admin)
    return admin.get(f"/api/admin/v1/imports/{batch}").json()["items"][0]


def stage_note(admin, batch, item, change):
    result = admin.patch(
        f"/api/admin/v1/imports/{batch}/items/{item['id']}",
        headers=key(),
        json={
            "revision": item["revision"],
            "content": item["content"],
            "selected": True,
            "study_note": change,
        },
    )
    assert result.status_code == 200, result.text
    return result.json()


def test_zip_restored_keep_with_valid_pdf_saves_internal_decision(admin):
    from .test_imports import document

    batch, item = import_package(
        admin,
        "restore.zip",
        [("scene/内容.docx", document("恢复后保存")), ("scene/笔记.pdf", pdf())],
    )
    original_id = item["study_note"]["attachment"]["id"]
    broken = upload(admin, b"invalid")
    process_jobs(admin)
    item = stage_note(admin, batch, item, {"action": "set", "media_id": broken["id"]})
    item = stage_note(admin, batch, item, {"action": "keep"})
    assert item["study_note"]["attachment"]["id"] == original_id
    saved = save_import(admin, batch)
    assert saved["state"] == "saved", saved
    card = admin.get(f"/api/admin/v1/cards/{saved['saved_card_id']}").json()
    assert card["study_note"]["attachment"]["id"] == original_id
    stable = save_note(admin, card, {"action": "keep"})
    assert stable["study_note"]["attachment"]["id"] == original_id


def test_zip_pdf_only_update_reuses_canonical_body_and_does_not_enqueue_tts(admin, mini, system):
    from sqlalchemy import func, select

    from juya_api.job_models import Job

    from .content_helpers import picture, recording
    from .test_imports import document

    base = [
        ("scene/内容.docx", document("同正文换PDF")),
        ("scene/场景图.png", picture()),
        ("scene/完整音频.wav", recording()),
    ]
    batch, item = import_package(admin, "original.zip", base + [("scene/笔记.pdf", pdf("first"))])
    saved = save_import(admin, batch)
    card = publish(admin, admin.get(f"/api/admin/v1/cards/{saved['saved_card_id']}").json())
    position = {
        "version_id": card["current_version_id"],
        "anchor": "dialogue:" + card["content"]["dialogue"][0]["id"],
        "progress": 0.5,
    }
    assert (
        mini.put(
            f"/api/mini/v1/cards/{card['id']}/reading-position", headers=key(), json=position
        ).status_code
        == 200
    )
    with system["sessions"]() as db:
        jobs_before = db.scalar(
            select(func.count()).select_from(Job).where(Job.kind == "pronunciation.prewarm")
        )
    second_batch, second = import_package(
        admin, "replacement.zip", base + [("scene/笔记.pdf", pdf("second"))]
    )
    assert second["content"]["image_id"] != card["content"]["image_id"]
    result = admin.patch(
        f"/api/admin/v1/imports/{second_batch}/items/{second['id']}",
        headers=key(),
        json={
            "revision": second["revision"],
            "content": second["content"],
            "selected": True,
            "target_card_id": card["id"],
            "target_revision": card["draft_revision"],
            "update_confirmed": True,
        },
    )
    assert result.status_code == 200, result.text
    saved = save_import(admin, second_batch)
    assert saved["state"] == "saved", saved
    candidate = admin.get(f"/api/admin/v1/cards/{card['id']}").json()
    assert candidate["content"] == card["content"]
    current = publish(admin, candidate)
    assert current["current_version_id"] == card["current_version_id"]
    assert current["sort_order"] == card["sort_order"]
    detail = mini.get(f"/api/mini/v1/cards/{card['id']}?mark_started=false").json()
    assert detail["reading_position"] == position and not detail["reading_position_reset"]
    assert (
        current["published_study_note"]["version_id"] != card["published_study_note"]["version_id"]
    )
    with system["sessions"]() as db:
        assert (
            db.scalar(
                select(func.count()).select_from(Job).where(Job.kind == "pronunciation.prewarm")
            )
            == jobs_before
        )


def test_zip_failed_replacement_preserves_effective_and_pending_references_on_card(admin):
    from .test_imports import document

    batch, item = import_package(
        admin,
        "pending.zip",
        [("scene/内容.docx", document("失败附件可存草稿")), ("scene/原笔记.pdf", pdf())],
    )
    original_id = item["study_note"]["attachment"]["id"]
    broken = upload(admin, b"invalid")
    process_jobs(admin)
    item = stage_note(admin, batch, item, {"action": "set", "media_id": broken["id"]})
    saved = save_import(admin, batch)
    assert saved["state"] == "saved"
    card = admin.get(f"/api/admin/v1/cards/{saved['saved_card_id']}").json()
    assert card["study_note"]["attachment"]["id"] == original_id
    assert card["study_note"]["pending_attachment"]["id"] == broken["id"]
    assert not card["study_note"]["can_publish"]
    cancelled = save_note(admin, card, {"action": "keep"})
    assert cancelled["study_note"]["attachment"]["id"] == original_id
    assert cancelled["study_note"]["pending_attachment"] is None


@pytest.mark.mysql
@pytest.mark.parametrize("pause_after", ["count", "rows"])
def test_mysql_notes_count_page_and_flag_share_one_snapshot_during_removal(
    admin, mini, system, pause_after
):
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy import event

    if system["engine"].dialect.name != "mysql":
        pytest.skip("Dedicated local MySQL required")
    medium = upload(admin)
    process_jobs(admin)
    base = content(admin)
    cards = [
        publish(
            admin,
            save_note(
                admin,
                draft(admin, dict(base, name=f"并发页{i}")),
                {"action": "set", "media_id": medium["id"]},
            ),
        )
        for i in range(2)
    ]
    path = "/api/mini/v1/cards?scope=published&has_study_note=true&limit=1&page=2"
    victim = mini.get(path).json()["items"][0]["id"]
    victim_card = next(c for c in cards if c["id"] == victim)
    fired = []

    def after_count(connection, cursor, statement, parameters, context, executemany):
        is_count = "count(" in statement.lower() and "card_study_note_versions" in statement
        is_rows = (
            "SELECT cards.id, cards.status" in statement and "ORDER BY cards.is_free" in statement
        )
        if not fired and (is_count if pause_after == "count" else is_rows):
            fired.append(True)

            def remove():
                return publish(admin, save_note(admin, victim_card, {"action": "remove"}))

            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(remove).result(timeout=10)

    event.listen(system["engine"], "after_cursor_execute", after_count)
    try:
        page = mini.get(path).json()
    finally:
        event.remove(system["engine"], "after_cursor_execute", after_count)
    assert fired
    assert page["total"] == 2 and page["page"] == 2
    assert len(page["items"]) == 1 and page["items"][0]["has_study_note"]
    refreshed = mini.get(path).json()
    assert refreshed["total"] == 1 and refreshed["page"] == 1 and len(refreshed["items"]) == 1


def test_restored_zip_note_is_not_deduplicated_as_an_omitted_attachment(admin):
    from .test_imports import document

    raw = document("同正文的明确保留PDF")
    first_batch, first_item = import_package(admin, "plain.zip", [("scene/内容.docx", raw)])
    first = save_import(admin, first_batch)
    assert first["state"] == "saved"
    batch, item = import_package(
        admin, "with-note.zip", [("scene/内容.docx", raw), ("scene/笔记.pdf", pdf())]
    )
    original_id = item["study_note"]["attachment"]["id"]
    bad = upload(admin, b"invalid")
    process_jobs(admin)
    item = stage_note(admin, batch, item, {"action": "set", "media_id": bad["id"]})
    item = stage_note(admin, batch, item, {"action": "keep"})
    confirmation = admin.get(f"/api/admin/v1/imports/{batch}/confirmation").json()
    assert confirmation["count"] == 1 and confirmation["duplicates"] == 0
    target = admin.get(f"/api/admin/v1/cards/{first['saved_card_id']}").json()
    staged = admin.patch(
        f"/api/admin/v1/imports/{batch}/items/{item['id']}",
        headers=key(),
        json={
            "revision": item["revision"],
            "content": item["content"],
            "selected": True,
            "target_card_id": target["id"],
            "target_revision": target["draft_revision"],
            "update_confirmed": True,
        },
    )
    assert staged.status_code == 200, staged.text
    saved = save_import(admin, batch)
    assert saved["state"] == "saved" and saved["saved_card_id"] == target["id"]
    assert (
        admin.get(f"/api/admin/v1/cards/{target['id']}").json()["study_note"]["attachment"]["id"]
        == original_id
    )


@pytest.mark.parametrize("pending_action", ["set", "unresolved"])
def test_resaving_pending_note_tracks_fallback_content_and_ignores_equivalent_upload_ids(
    admin, pending_action
):
    from .test_imports import document

    batch, item = import_package(
        admin,
        "resave.zip",
        [("scene/内容.docx", document("保留有效附件的重存")), ("scene/A.pdf", pdf("A"))],
    )
    failed = upload(admin, b"invalid-B")
    process_jobs(admin)
    pending_change = (
        {"action": "set", "media_id": failed["id"]}
        if pending_action == "set"
        else {"action": "unresolved"}
    )
    item = stage_note(admin, batch, item, pending_change)
    saved = save_import(admin, batch)
    card_id = saved["saved_card_id"]
    assert saved["state"] == "saved"
    c = upload(admin, pdf("C"))
    process_jobs(admin)
    item = stage_note(admin, batch, saved, {"action": "set", "media_id": c["id"]})
    item = stage_note(admin, batch, item, pending_change)
    assert item["study_note"]["attachment"]["id"] == c["id"]
    confirmation = admin.get(f"/api/admin/v1/imports/{batch}/confirmation").json()
    assert confirmation["count"] == 1
    saved = save_import(admin, batch)
    assert saved["state"] == "saved" and saved["saved_card_id"] == card_id
    card = admin.get(f"/api/admin/v1/cards/{card_id}").json()
    assert card["study_note"]["attachment"]["id"] == c["id"]
    if pending_action == "set":
        assert card["study_note"]["pending_attachment"]["id"] == failed["id"]
    else:
        assert card["study_note"]["action"] == "unresolved"
    same_c = upload(admin, pdf("C"))
    assert same_c["id"] != c["id"]
    process_jobs(admin)
    item = stage_note(admin, batch, saved, {"action": "set", "media_id": same_c["id"]})
    item = stage_note(admin, batch, item, pending_change)
    assert item["state"] == "saved"
    assert admin.get(f"/api/admin/v1/imports/{batch}/confirmation").json()["count"] == 0
    cancelled = save_note(admin, card, {"action": "keep"})
    assert cancelled["study_note"]["attachment"]["id"] == c["id"]


def test_pdf_ticket_requires_issuing_bearer_on_every_read(admin, mini):
    from .test_auth import login
    from .test_learning_access import change as authorize
    from .test_learning_access import user_id

    medium = upload(admin)
    process_jobs(admin)
    card = publish(
        admin, save_note(admin, draft(admin), {"action": "set", "media_id": medium["id"]})
    )
    authorize(admin, user_id(mini), "grant")
    path = f"/api/admin/v1/cards/{card['id']}/free-access"
    admin.put(
        path, headers=key(), json={"is_free": False, "revision": admin.get(path).json()["revision"]}
    )
    url = ticket(mini, card, card["published_study_note"])

    native_urls = [
        mini.get(
            f"/api/mini/v1/cards/{card['id']}/media/{card['content'][field]}/url",
            params={"version_id": card["current_version_id"]},
        ).json()["url"]
        for field in ("image_id", "audio_id")
    ]

    def read():
        return [
            mini.get(url).status_code,
            mini.head(url).status_code,
            mini.get(url, headers={"Range": "bytes=0-3"}).status_code,
        ]

    assert read() == [200, 200, 206]
    mini.headers.pop("Authorization")
    assert read() == [401, 401, 401]
    for native_url in native_urls:
        assert mini.get(native_url).status_code == 200
        assert mini.head(native_url).status_code == 200
        assert mini.get(native_url, headers={"Range": "bytes=0-3"}).status_code == 206
    for code in ("bob:other", "alice:other"):
        access = login(mini, code, key()["Idempotency-Key"]).json()["access_token"]
        mini.headers["Authorization"] = "Bearer " + access
        if code.startswith("bob:"):
            assert (
                mini.get(f"/api/mini/v1/cards/{card['id']}?mark_started=false").status_code == 403
            )
        assert read() == [401, 401, 401]
