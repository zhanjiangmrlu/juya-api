"""Persist a validated editor fallback atomically and report real PDF rejection causes."""

import io

import pytest
from fastapi.testclient import TestClient

from .content_helpers import draft, key, picture, process_jobs, publish
from .test_study_notes import import_package, pdf, save_import, save_note, upload


def encrypted_pdf():
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(pdf())))
    writer.encrypt("isolated-test-password")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def published_a(admin):
    a = upload(admin, pdf("A"))
    process_jobs(admin)
    return publish(admin, save_note(admin, draft(admin), {"action": "set", "media_id": a["id"]}))


@pytest.mark.parametrize("origin", ["card", "zip"])
def test_unsaved_ready_b_and_failed_c_save_atomically_reopen_and_cancel_to_b(admin, mini, origin):
    from .test_imports import document

    card = published_a(admin)
    b = upload(admin, pdf("B"))
    process_jobs(admin)  # B is valid locally, but no card/import save has ever bound it.
    c = upload(admin, b"broken-C")
    process_jobs(admin)
    change = {"action": "set", "media_id": c["id"], "previous_media_id": b["id"]}
    if origin == "card":
        headers = key()
        body = {
            "revision": card["draft_revision"],
            "content": card["content"],
            "study_note": change,
        }
        response = admin.put(f"/api/admin/v1/cards/{card['id']}", headers=headers, json=body)
        assert response.status_code == 200, response.text
        assert (
            admin.put(f"/api/admin/v1/cards/{card['id']}", headers=headers, json=body).json()
            == response.json()
        )
    else:
        batch, item = import_package(
            admin, "old-package.zip", [("scene/内容.docx", document("更新目标"))]
        )
        response = admin.patch(
            f"/api/admin/v1/imports/{batch}/items/{item['id']}",
            headers=key(),
            json={
                "revision": item["revision"],
                "content": card["content"],
                "selected": True,
                "target_card_id": card["id"],
                "target_revision": card["draft_revision"],
                "update_confirmed": True,
                "study_note": change,
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["study_note"]["attachment"]["id"] == b["id"]
        assert save_import(admin, batch)["state"] == "saved"
    reopened = admin.get(f"/api/admin/v1/cards/{card['id']}").json()
    assert reopened["study_note"]["attachment"]["id"] == b["id"]
    assert reopened["study_note"]["pending_attachment"]["id"] == c["id"]
    assert not reopened["study_note"]["can_publish"]
    assert reopened["published_study_note"] == card["published_study_note"]
    cancelled = save_note(admin, reopened, {"action": "keep"})
    assert cancelled["study_note"]["attachment"]["id"] == b["id"]
    assert cancelled["study_note"]["pending_attachment"] is None
    assert cancelled["current_version_id"] == card["current_version_id"]
    assert cancelled["sort_order"] == card["sort_order"]
    detail = mini.get(f"/api/mini/v1/cards/{card['id']}?mark_started=false").json()
    assert detail["study_note"] == card["published_study_note"]


@pytest.mark.parametrize("action", ["set", "unresolved"])
@pytest.mark.parametrize("invalid", ["processing", "failed", "image", "missing", "foreign"])
def test_explicit_previous_pdf_must_be_ready_owned_and_pdf(admin, system, action, invalid):
    card = published_a(admin)
    pending = upload(admin, b"pending")
    if invalid == "processing":
        previous = upload(admin)
    elif invalid == "failed":
        previous = upload(admin, b"bad")
        process_jobs(admin)
    elif invalid == "image":
        previous = admin.post(
            "/api/admin/v1/media?kind=image",
            headers=key(),
            files={"file": ("photo.png", picture(), "image/png")},
        ).json()
        process_jobs(admin)
    elif invalid == "missing":
        previous = {"id": "00000000-0000-0000-0000-000000000000"}
    else:
        from juya_api.auth import passwords
        from juya_api.models import Administrator

        with system["sessions"].begin() as db:
            db.add(
                Administrator(
                    username="other-admin", password_hash=passwords.hash("isolated-other-password")
                )
            )
        with TestClient(admin.app, base_url="https://testserver") as other:
            login = other.post(
                "/api/admin/v1/auth/login",
                json={"username": "other-admin", "password": "isolated-other-password"},
            ).json()
            other.headers["X-CSRF-Token"] = login["csrf_token"]
            previous = upload(other)
            process_jobs(other)
    change = {"action": action, "previous_media_id": previous["id"]}
    if action == "set":
        change["media_id"] = pending["id"]
    response = admin.put(
        f"/api/admin/v1/cards/{card['id']}",
        headers=key(),
        json={"revision": card["draft_revision"], "content": card["content"], "study_note": change},
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "study_note_previous_invalid"
    assert (
        admin.get(f"/api/admin/v1/cards/{card['id']}").json()["draft_revision"]
        == card["draft_revision"]
    )


@pytest.mark.parametrize("action", ["keep", "remove"])
@pytest.mark.parametrize("previous", [None, "00000000-0000-0000-0000-000000000000"])
def test_keep_and_remove_reject_a_previous_field(admin, action, previous):
    card = draft(admin)
    response = admin.put(
        f"/api/admin/v1/cards/{card['id']}",
        headers=key(),
        json={
            "revision": card["draft_revision"],
            "content": card["content"],
            "study_note": {"action": action, "previous_media_id": previous},
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "case,code,message",
    [
        ("format", "study_note_format_invalid", "文件实际格式不是PDF，请选择PDF文件"),
        ("corrupt", "study_note_invalid", "PDF文件结构损坏或内容无法读取，请更换完整PDF"),
        ("encrypted", "study_note_encrypted", "PDF已加密且无法打开，请解除密码保护后重新上传"),
    ],
)
def test_pdf_rejection_has_specific_safe_reason_in_media_and_zip(admin, case, code, message):
    from .test_imports import document

    body = {"format": b"not-pdf", "corrupt": b"%PDF-1.4\nbroken", "encrypted": encrypted_pdf()}[
        case
    ]
    medium = upload(admin, body)
    process_jobs(admin)
    status = admin.get(f"/api/admin/v1/media/{medium['id']}/status").json()
    assert status["error_code"] == code and status["error"] == message
    batch, item = import_package(
        admin, f"{case}.zip", [("scene/内容.docx", document("PDF原因")), ("scene/笔记.pdf", body)]
    )
    imported = admin.get(f"/api/admin/v1/imports/{batch}").json()
    file = next(row for row in imported["files"] if row["kind"] == "study_note")
    assert file["error_code"] == code and file["error"] == message
    assert item["study_note"]["candidates"][0]["error"] == message
    assert any(issue["message"] == message for issue in item["issues"])


@pytest.mark.parametrize("empty", [True, False])
def test_empty_and_oversized_pdf_report_distinct_actual_reason(admin, system, empty):
    system["settings"].study_note_limit_mb = 1
    body = b"" if empty else b"x" * (1048576 + 1)
    result = admin.post(
        "/api/admin/v1/media?kind=study_note",
        headers=key(),
        files={"file": ("note.pdf", body, "application/pdf")},
    )
    assert result.status_code == 413
    assert result.json()["error"]["code"] == ("study_note_empty" if empty else "study_note_limit")


def test_unresolved_can_atomically_keep_a_new_ready_fallback(admin):
    card = published_a(admin)
    b = upload(admin, pdf("B"))
    process_jobs(admin)
    changed = save_note(admin, card, {"action": "unresolved", "previous_media_id": b["id"]})
    assert changed["study_note"]["attachment"]["id"] == b["id"]
    assert not changed["study_note"]["can_publish"]
    assert (
        save_note(admin, changed, {"action": "keep"})["study_note"]["attachment"]["id"] == b["id"]
    )


@pytest.mark.parametrize("source", ["other_folder", "other_zip"])
def test_zip_previous_cannot_bind_an_unrelated_folder_or_package(admin, source):
    from .test_imports import document

    batch, first = import_package(
        admin,
        "two.zip",
        [
            ("one/内容.docx", document("第一张")),
            ("one/A.pdf", pdf("one")),
            ("two/内容.docx", document("第二张")),
            ("two/B.pdf", pdf("two")),
        ],
    )
    if source == "other_folder":
        other = admin.get(f"/api/admin/v1/imports/{batch}").json()["items"][1]
    else:
        _, other = import_package(
            admin, "other.zip", [("one/内容.docx", document("别的包")), ("one/C.pdf", pdf("other"))]
        )
    c = upload(admin, b"bad-C")
    process_jobs(admin)
    response = admin.patch(
        f"/api/admin/v1/imports/{batch}/items/{first['id']}",
        headers=key(),
        json={
            "revision": first["revision"],
            "content": first["content"],
            "selected": True,
            "study_note": {
                "action": "set",
                "media_id": c["id"],
                "previous_media_id": other["study_note"]["attachment"]["id"],
            },
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "import_media_source"


def test_zip_previous_may_keep_the_confirmed_targets_original_pdf_from_an_old_package(admin):
    from .content_helpers import recording
    from .test_imports import document

    raw, image, audio = document("历史目标"), picture(), recording()
    batch, _ = import_package(
        admin,
        "original.zip",
        [
            ("old/内容.docx", raw),
            ("old/场景图.png", image),
            ("old/完整音频.wav", audio),
            ("old/A.pdf", pdf("A")),
        ],
    )
    original = save_import(admin, batch)
    card = publish(admin, admin.get(f"/api/admin/v1/cards/{original['saved_card_id']}").json())
    batch, item = import_package(
        admin,
        "new.zip",
        [("new/内容.docx", raw), ("new/场景图.png", image), ("new/完整音频.wav", audio)],
    )
    c = upload(admin, b"bad-C")
    process_jobs(admin)
    result = admin.patch(
        f"/api/admin/v1/imports/{batch}/items/{item['id']}",
        headers=key(),
        json={
            "revision": item["revision"],
            "content": item["content"],
            "selected": True,
            "target_card_id": card["id"],
            "target_revision": card["draft_revision"],
            "update_confirmed": True,
            "study_note": {
                "action": "set",
                "media_id": c["id"],
                "previous_media_id": card["published_study_note"]["media_id"],
            },
        },
    )
    assert result.status_code == 200, result.text
    assert (
        result.json()["study_note"]["attachment"]["id"] == card["published_study_note"]["media_id"]
    )
    assert save_import(admin, batch)["state"] == "saved"


@pytest.mark.parametrize("empty", [True, False])
def test_zip_empty_and_oversized_pdf_expose_actual_error_without_discarding_draft(
    admin, system, empty
):
    import os

    from .test_imports import document

    system["settings"].study_note_limit_mb = 1
    body = b"" if empty else os.urandom(1048576 + 1)
    code = "study_note_empty" if empty else "study_note_limit"
    expected = "PDF文件为空，请重新选择" if empty else "PDF文件超过当前大小限制，请压缩或更换文件"
    batch, item = import_package(
        admin,
        "bounded.zip",
        [("scene/内容.docx", document("失败仍保留正文")), ("scene/笔记.pdf", body)],
    )
    file = next(
        row
        for row in admin.get(f"/api/admin/v1/imports/{batch}").json()["files"]
        if row["kind"] == "study_note"
    )
    assert file["error_code"] == code and file["error"] == expected
    assert item["study_note"]["candidates"][0]["error"] == expected
    assert any(
        issue["field"] == "study_note" and issue["message"] == expected for issue in item["issues"]
    )
    assert save_import(admin, batch)["state"] == "saved"


@pytest.mark.parametrize("action", ["set", "unresolved"])
def test_explicit_null_previous_is_rejected_instead_of_silently_clearing_fallback(admin, action):
    card = draft(admin)
    selected = upload(admin)
    change = {"action": action, "previous_media_id": None}
    if action == "set":
        change["media_id"] = selected["id"]
    result = admin.put(
        f"/api/admin/v1/cards/{card['id']}",
        headers=key(),
        json={"revision": card["draft_revision"], "content": card["content"], "study_note": change},
    )
    assert result.status_code == 422


def historical_note_target(admin, *, published=True):
    from .content_helpers import recording
    from .test_imports import document

    batch, _ = import_package(
        admin,
        "history.zip",
        [
            ("history/内容.docx", document("原目标")),
            ("history/场景图.png", picture()),
            ("history/完整音频.wav", recording()),
            ("history/A.pdf", pdf("history")),
        ],
    )
    saved = save_import(admin, batch)
    target = admin.get(f"/api/admin/v1/cards/{saved['saved_card_id']}").json()
    return publish(admin, target) if published else target


def choose_historical_fallback(admin, target, *, cancel=False):
    from .test_imports import document

    batch, item = import_package(
        admin, "current.zip", [("current/内容.docx", document("新核对项"))]
    )
    c = upload(admin, b"bad-C")
    process_jobs(admin)
    body = {
        "revision": item["revision"],
        "content": item["content"],
        "selected": True,
        "target_card_id": target["id"],
        "target_revision": target["draft_revision"],
        "update_confirmed": True,
        "study_note": {
            "action": "set",
            "media_id": c["id"],
            "previous_media_id": target["published_study_note"]["media_id"],
        },
    }
    response = admin.patch(
        f"/api/admin/v1/imports/{batch}/items/{item['id']}", headers=key(), json=body
    )
    assert response.status_code == 200, response.text
    item = response.json()
    if cancel:
        body.update(revision=item["revision"], study_note={"action": "keep"})
        response = admin.patch(
            f"/api/admin/v1/imports/{batch}/items/{item['id']}", headers=key(), json=body
        )
        assert response.status_code == 200, response.text
        item = response.json()
    return batch, item


@pytest.mark.parametrize("new_target", ["clear", "other"])
@pytest.mark.parametrize("cancel", [False, True])
def test_zip_retained_note_is_rechecked_when_final_target_changes(admin, new_target, cancel):
    target = historical_note_target(admin)
    batch, item = choose_historical_fallback(admin, target, cancel=cancel)
    body = {"revision": item["revision"], "content": item["content"], "selected": True}
    if new_target == "other":
        other = draft(admin)
        body.update(
            target_card_id=other["id"],
            target_revision=other["draft_revision"],
            update_confirmed=True,
        )
    response = admin.patch(
        f"/api/admin/v1/imports/{batch}/items/{item['id']}", headers=key(), json=body
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "import_media_source"


@pytest.mark.parametrize("cancel", [False, True])
def test_zip_worker_rechecks_provenance_of_legacy_retained_state_after_target_clear(
    admin, system, cancel
):
    from juya_api.import_models import ImportItem

    target = historical_note_target(admin)
    batch, item = choose_historical_fallback(admin, target, cancel=cancel)
    # Represent the exact persisted state previously accepted by the two-PATCH path.
    with system["sessions"].begin() as db:
        row = db.get(ImportItem, item["id"])
        row.target_card_id = row.target_revision = None
    before = admin.get("/api/admin/v1/cards").json()["total"]
    saved = save_import(admin, batch)
    assert saved["state"] == "failed", saved
    assert saved["error_code"] == "import_media_source"
    assert admin.get("/api/admin/v1/cards").json()["total"] == before


def test_deleting_external_zip_does_not_turn_its_pdf_into_a_manual_upload(admin):
    from .test_imports import document

    external_batch, external = import_package(
        admin,
        "external.zip",
        [("external/内容.docx", document("外部来源")), ("external/A.pdf", pdf("external"))],
    )
    media_id = external["study_note"]["attachment"]["id"]
    root = next(
        row
        for row in admin.get(f"/api/admin/v1/imports/{external_batch}").json()["files"]
        if not row["parent_id"]
    )
    batch, item = import_package(admin, "local.zip", [("local/内容.docx", document("当前来源"))])
    body = {
        "revision": item["revision"],
        "content": item["content"],
        "selected": True,
        "study_note": {"action": "unresolved", "previous_media_id": media_id},
    }
    endpoint = f"/api/admin/v1/imports/{batch}/items/{item['id']}"
    assert admin.patch(endpoint, headers=key(), json=body).status_code == 422
    removed = admin.post(
        f"/api/admin/v1/imports/{external_batch}/files/remove",
        headers=key(),
        json={"file_ids": [root["id"]]},
    )
    assert removed.status_code == 200, removed.text
    assert admin.get(f"/api/admin/v1/media/{media_id}/status").json()["state"] == "ready"
    result = admin.patch(endpoint, headers=key(), json=body)
    assert result.status_code == 422, result.text
    assert result.json()["error"]["code"] == "import_media_source"


def certificate_encrypted_pdf():
    from datetime import UTC, datetime, timedelta

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs7
    from cryptography.x509.oid import NameOID
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import (
        ArrayObject,
        ByteStringObject,
        DictionaryObject,
        NameObject,
        NumberObject,
    )

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "isolated PDF recipient")])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(private_key, hashes.SHA256())
    )
    envelope = (
        pkcs7.PKCS7EnvelopeBuilder()
        .set_data(b"isolated-file-key-and-permissions")
        .add_recipient(certificate)
        .encrypt(serialization.Encoding.DER, [pkcs7.PKCS7Options.Binary])
    )
    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(pdf())))
    writer._encrypt_entry = writer._add_object(
        DictionaryObject(
            {
                NameObject("/Filter"): NameObject("/Adobe.PubSec"),
                NameObject("/SubFilter"): NameObject("/adbe.pkcs7.s4"),
                NameObject("/V"): NumberObject(2),
                NameObject("/Length"): NumberObject(128),
                NameObject("/Recipients"): ArrayObject([ByteStringObject(envelope)]),
            }
        )
    )
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def test_certificate_encryption_is_reported_as_unreadable_encryption_not_corruption(admin):
    medium = upload(admin, certificate_encrypted_pdf())
    process_jobs(admin)
    status = admin.get(f"/api/admin/v1/media/{medium['id']}/status").json()
    assert status["error_code"] == "study_note_encrypted"
    assert status["error"] == "PDF已加密且无法打开，请解除密码保护后重新上传"


def test_old_zip_review_inherits_only_current_target_note_and_keeps_omission(admin, system):
    from juya_api.import_models import ImportItem

    from .test_imports import document

    original = historical_note_target(admin, published=False)
    assert original["study_note"]["candidates"]
    b = upload(admin)
    c = upload(admin, b"invalid")
    process_jobs(admin)
    pending = save_note(admin, original, {"action": "set", "media_id": c["id"]})
    ready = save_note(admin, draft(admin), {"action": "set", "media_id": b["id"]})
    batch, item = import_package(admin, "old.zip", [("dir/内容.docx", document("新正文"))])
    path = f"/api/admin/v1/imports/{batch}/items/{item['id']}"
    for target in (pending, ready, None, pending):
        body = {"revision": item["revision"], "content": ready["content"], "selected": True}
        if target:
            body.update(
                target_card_id=target["id"],
                target_revision=target["draft_revision"],
                update_confirmed=True,
            )
        response = admin.patch(path, headers=key(), json=body)
        assert response.status_code == 200, response.text
        item = response.json()
        note = item["study_note"]
        assert note["candidates"] == []
        if target:
            expected = target["study_note"]
            assert note["attachment"] == expected["attachment"]
            assert note["pending_attachment"] == expected["pending_attachment"]
            assert note["can_publish"] == expected["can_publish"]
        else:
            assert note["attachment"] is None and note["pending_attachment"] is None
            assert note["can_publish"]
        issues = [issue["message"] for issue in item["issues"] if issue["field"] == "study_note"]
        expected_issues = (
            [pending["study_note"]["pending_attachment"]["error"]] if target == pending else []
        )
        assert issues == expected_issues
        assert item["state"] == ("incomplete" if issues else "ready")
        with system["sessions"]() as db:
            assert db.get(ImportItem, item["id"]).study_note is None
    saved = save_import(admin, batch)
    actual = admin.get(f"/api/admin/v1/cards/{saved['saved_card_id']}").json()["study_note"]
    assert actual["attachment"] == note["attachment"]
    assert actual["pending_attachment"] == note["pending_attachment"]
    assert actual["can_publish"] == note["can_publish"]
