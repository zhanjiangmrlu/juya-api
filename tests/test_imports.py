"""Fixed DOCX parsing and hostile ZIP input never use filesystem extraction."""

import io
import stat
import zipfile

import pytest
from docx import Document


def document(*names):
    doc = Document()
    for name in names:
        doc.add_heading(name, level=1)
        doc.add_heading("场景对话", level=2)
        table = doc.add_table(rows=1, cols=3)
        for cell, text in zip(table.rows[0].cells, ["人物", "英文", "中文"], strict=True):
            cell.text = text
        for cell, text in zip(
            table.add_row().cells,
            ["Ivy", "Could I get a latte, please?", "请给我一杯拿铁。"],
            strict=True,
        ):
            cell.text = text
        doc.add_heading("重点词汇", level=2)
        table = doc.add_table(rows=1, cols=4)
        for cell, text in zip(
            table.rows[0].cells,
            ["词汇", "本句释义", "音标（选填）", "对应英文原句（建议填写）"],
            strict=True,
        ):
            cell.text = text
        for cell, text in zip(
            table.add_row().cells,
            ["latte", "拿铁咖啡", "", "Could I get a latte, please?"],
            strict=True,
        ):
            cell.text = text
    output = io.BytesIO()
    doc.save(output)
    return output.getvalue()


def archive(entries):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as data:
        for name, content in entries:
            data.writestr(name, content)
    return output.getvalue()


def parser():
    try:
        from juya_api.import_parser import checked_archive, parse_docx
    except ImportError as error:
        pytest.fail(f"Fixed safe import parsing missing: {error}")
    return parse_docx, checked_archive


def test_docx_uses_explicit_h1_boundaries_and_preserves_dialogue_and_confirmed_source():
    parse, _ = parser()
    values = parse(document("咖啡店", "机场"))
    assert [v["name"] for v in values] == ["咖啡店", "机场"]
    assert values[0]["dialogue"][0]["chinese"] == "请给我一杯拿铁。"
    word = values[0]["vocabulary"][0]
    assert word["meaning"] == "拿铁咖啡"
    assert word["source"]["quote"] == "latte"
    assert values[0]["chunks"] == []
    assert values[0]["dialogue"][0]["id"] != values[1]["dialogue"][0]["id"]
    doc = Document()
    doc.add_paragraph("卡片名称，任意空行不能当分篇标题")
    stream = io.BytesIO()
    doc.save(stream)
    from juya_api.errors import DomainError

    with pytest.raises(DomainError, match="docx_structure"):
        parse(stream.getvalue())


@pytest.mark.parametrize(
    "path",
    [
        "../escape.docx",
        "/absolute.docx",
        "C:/bad.docx",
        "a/../../bad.docx",
        "a\\bad.docx",
        "a//bad.docx",
    ],
)
def test_zip_rejects_unsafe_names_without_extracting(path):
    _, checked = parser()
    from juya_api.errors import DomainError

    with pytest.raises(DomainError, match="archive_unsafe"):
        checked(archive([(path, b"content")]))


def test_zip_rejects_duplicate_paths_symlinks_and_expansion_bombs():
    _, checked = parser()
    from juya_api.errors import DomainError

    with (
        pytest.warns(UserWarning, match="Duplicate name"),
        pytest.raises(DomainError, match="archive_unsafe"),
    ):
        checked(archive([("one/doc.docx", b"one"), ("one/doc.docx", b"two")]))
    link = zipfile.ZipInfo("one/link")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with pytest.raises(DomainError, match="archive_unsafe"):
        checked(archive([(link, b"../../elsewhere")]))
    with pytest.raises(DomainError, match="archive_limit"):
        checked(archive([("one/padding", b"x" * 2_000_000)]), expanded_limit=1_000_000)


def test_docx_external_entities_and_unreadable_documents_are_rejected():
    parse, _ = parser()
    from juya_api.errors import DomainError

    xml = b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>&e;</w:t></w:r></w:p></w:body></w:document>'
    with pytest.raises(DomainError, match="docx_invalid"):
        parse(archive([("word/document.xml", xml)]))
    with pytest.raises(DomainError, match="docx_invalid"):
        parse(b"not a zip file")


def test_docx_batch_restores_staging_matches_only_exact_names_and_saves_drafts(admin, mini):
    from .content_helpers import key, picture, process_jobs, recording

    created = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "docx"})
    assert created.status_code == 201, created.text
    batch_id = created.json()["id"]
    for kind, name, data in [
        ("docx", "场景.docx", document("咖啡店", "机场")),
        ("image", "咖啡店.png", picture()),
        ("audio", "咖啡店.wav", recording()),
    ]:
        response = admin.post(
            f"/api/admin/v1/imports/{batch_id}/files?kind={kind}",
            headers=key(),
            files={"file": (name, data, "application/octet-stream")},
        )
        assert response.status_code == 201, response.text
    process_jobs(admin)
    matched = admin.post(f"/api/admin/v1/imports/{batch_id}/resolve", headers=key())
    assert matched.status_code == 200, matched.text
    items = matched.json()["items"]
    assert len(items) == 2 and items[0]["content"]["image_id"]
    assert items[0]["thumbnail_id"]
    assert items[1]["content"]["image_id"] is None
    # Persisted staging survives a new read and changes invalidate an old confirmation.
    confirmation = admin.get(f"/api/admin/v1/imports/{batch_id}/confirmation").json()
    updated = admin.patch(
        f"/api/admin/v1/imports/{batch_id}/items/{items[1]['id']}",
        headers=key(),
        json={
            "revision": items[1]["revision"],
            "content": dict(items[1]["content"], name="机场（已核对）"),
            "selected": True,
        },
    )
    assert updated.status_code == 200, updated.text
    restored = admin.get(f"/api/admin/v1/imports/{batch_id}").json()
    assert restored["items"][1]["content"]["name"] == "机场（已核对）"
    assert (
        admin.post(
            f"/api/admin/v1/imports/{batch_id}/save",
            headers=key(),
            json={"confirmed": True, "version": confirmation["version"]},
        ).status_code
        == 409
    )
    confirmation = admin.get(f"/api/admin/v1/imports/{batch_id}/confirmation").json()
    headers = key()
    accepted = admin.post(
        f"/api/admin/v1/imports/{batch_id}/save",
        headers=headers,
        json={"confirmed": True, "version": confirmation["version"]},
    )
    assert accepted.status_code == 200, accepted.text
    assert (
        admin.post(
            f"/api/admin/v1/imports/{batch_id}/save",
            headers=headers,
            json={"confirmed": True, "version": confirmation["version"]},
        ).json()
        == accepted.json()
    )
    process_jobs(admin)
    result = admin.get(f"/api/admin/v1/imports/{batch_id}").json()
    assert all(item["state"] == "saved" for item in result["items"])
    from .content_helpers import draft

    unrelated = draft(admin)
    filtered = admin.get(f"/api/admin/v1/cards?batch_id={batch_id}")
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["total"] == 2
    assert unrelated["id"] not in [item["id"] for item in filtered.json()["items"]]
    assert admin.get("/api/admin/v1/cards?batch_id=unowned").status_code == 404
    assert admin.get("/api/admin/v1/cards").json()["total"] == 3
    assert mini.get("/api/mini/v1/cards").json()["total"] == 0


def test_zip_keeps_other_folders_when_one_docx_has_multiple_cards_and_never_merges_same_name(admin):
    from .content_helpers import key, picture, process_jobs, recording

    batch = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()
    response = admin.post(
        f"/api/admin/v1/imports/{batch['id']}/files?kind=zip",
        headers=key(),
        files={
            "file": (
                "资料.zip",
                archive(
                    [
                        ("one/内容.docx", document("同名卡片")),
                        ("one/场景图.png", picture()),
                        ("one/完整音频.wav", recording()),
                        ("two/内容.docx", document("同名卡片", "另一张")),
                        ("three/内容.docx", document("同名卡片")),
                    ]
                ),
                "application/zip",
            )
        },
    )
    assert response.status_code == 201, response.text
    process_jobs(admin)
    result = admin.get(f"/api/admin/v1/imports/{batch['id']}").json()
    assert len(result["items"]) == 3
    assert sum(not i["readable"] for i in result["items"]) == 1
    confirmation = admin.get(f"/api/admin/v1/imports/{batch['id']}/confirmation").json()
    assert confirmation["unreadable"] == 1 and confirmation["excluded"] == 0
    admin.post(
        f"/api/admin/v1/imports/{batch['id']}/save",
        headers=key(),
        json={"confirmed": True, "version": confirmation["version"]},
    )
    process_jobs(admin)
    # Same name does not imply identity; distinct media or document bytes stay separate.
    assert admin.get("/api/admin/v1/cards").json()["total"] == 2


def test_explicit_update_conflict_preserves_other_saved_items_and_retry_skips_success(admin, mini):
    from .content_helpers import draft, key, process_jobs, publish

    target = draft(admin)
    published = publish(admin, target)
    batch = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "docx"}).json()
    batch_id = batch["id"]
    admin.post(
        f"/api/admin/v1/imports/{batch_id}/files?kind=docx",
        headers=key(),
        files={"file": ("two.docx", document("更新目标", "独立新增"), "application/octet-stream")},
    )
    process_jobs(admin)
    items = admin.get(f"/api/admin/v1/imports/{batch_id}").json()["items"]
    body = {
        "revision": items[0]["revision"],
        "content": items[0]["content"],
        "selected": True,
        "target_card_id": target["id"],
        "target_revision": 1,
    }
    assert (
        admin.patch(
            f"/api/admin/v1/imports/{batch_id}/items/{items[0]['id']}", headers=key(), json=body
        ).status_code
        == 422
    )
    body["update_confirmed"] = True
    assert (
        admin.patch(
            f"/api/admin/v1/imports/{batch_id}/items/{items[0]['id']}", headers=key(), json=body
        ).status_code
        == 200
    )
    confirmation = admin.get(f"/api/admin/v1/imports/{batch_id}/confirmation").json()
    admin.post(
        f"/api/admin/v1/imports/{batch_id}/save",
        headers=key(),
        json={"confirmed": True, "version": confirmation["version"]},
    )
    admin.put(
        f"/api/admin/v1/cards/{target['id']}",
        headers=key(),
        json={"revision": 1, "content": dict(target["content"], name="另一窗口修改")},
    )
    process_jobs(admin)
    result = admin.get(f"/api/admin/v1/imports/{batch_id}").json()["items"]
    assert [item["state"] for item in result] == ["failed", "saved"]
    succeeded_job = result[1]["job_id"]
    body.update(revision=result[0]["revision"], target_revision=2)
    assert (
        admin.patch(
            f"/api/admin/v1/imports/{batch_id}/items/{items[0]['id']}", headers=key(), json=body
        ).status_code
        == 200
    )
    confirmation = admin.get(f"/api/admin/v1/imports/{batch_id}/confirmation").json()
    assert confirmation["count"] == 1
    admin.post(
        f"/api/admin/v1/imports/{batch_id}/save",
        headers=key(),
        json={"confirmed": True, "version": confirmation["version"]},
    )
    process_jobs(admin)
    result = admin.get(f"/api/admin/v1/imports/{batch_id}").json()["items"]
    assert [item["state"] for item in result] == ["saved", "saved"]
    assert result[1]["job_id"] == succeeded_job
    assert admin.get("/api/admin/v1/cards").json()["total"] == 2
    assert (
        mini.get(f"/api/mini/v1/cards/{target['id']}").json()["version_id"]
        == published["current_version_id"]
    )


def test_same_complete_object_is_skipped_across_batches_without_name_merging(admin):
    from .content_helpers import key, picture, process_jobs, recording

    raw = document("完整对象")
    package = archive(
        [
            ("完整对象/内容.docx", raw),
            ("完整对象/场景图.png", picture()),
            ("完整对象/完整音频.wav", recording()),
        ]
    )
    batches = []
    for index in range(2):
        batch = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()
        batch_id = batch["id"]
        batches.append(batch_id)
        admin.post(
            f"/api/admin/v1/imports/{batch_id}/files?kind=zip",
            headers=key(),
            files={"file": (f"重命名{index}.zip", package, "application/zip")},
        )
        process_jobs(admin)
        confirmation = admin.get(f"/api/admin/v1/imports/{batch_id}/confirmation").json()
        if index == 0:
            assert confirmation["count"] == 1
            admin.post(
                f"/api/admin/v1/imports/{batch_id}/save",
                headers=key(),
                json={"confirmed": True, "version": confirmation["version"]},
            )
            process_jobs(admin)
        else:
            assert confirmation["count"] == 0 and confirmation["duplicates"] == 1
    assert admin.get("/api/admin/v1/cards").json()["total"] == 1


def test_single_editor_docx_preview_rejects_multiple_cards_without_taking_first(admin):
    from .content_helpers import key, process_jobs

    created = admin.post(
        "/api/admin/v1/imports", headers=key(), json={"mode": "docx", "single_card": True}
    )
    assert created.status_code == 201, created.text
    batch_id = created.json()["id"]
    admin.post(
        f"/api/admin/v1/imports/{batch_id}/files?kind=docx",
        headers=key(),
        files={"file": ("多卡.docx", document("第一张", "第二张"), "application/octet-stream")},
    )
    process_jobs(admin)
    result = admin.get(f"/api/admin/v1/imports/{batch_id}").json()
    assert result["items"] == []
    assert result["files"][0]["error_code"] == "single_docx_multiple"
    assert admin.get("/api/admin/v1/cards").json()["total"] == 0


def test_download_example_is_authenticated_parseable_and_does_not_seed_business_data(admin, system):
    response = admin.get("/api/admin/v1/imports/example")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    parse, _ = parser()
    with zipfile.ZipFile(io.BytesIO(response.content)) as package:
        assert {
            "在咖啡店点单/内容.docx",
            "在咖啡店点单/场景图.png",
            "在咖啡店点单/完整音频.wav",
        } <= set(package.namelist())
        assert len(parse(package.read("在咖啡店点单/内容.docx"))) == 1
    assert admin.get("/api/admin/v1/cards").json()["total"] == 0
    from fastapi.testclient import TestClient

    with TestClient(system["admin"].app, base_url="https://testserver") as unsigned:
        assert unsigned.get("/api/admin/v1/imports/example").status_code == 401


def test_failed_import_file_retries_retained_bytes_without_duplicating_successful_items(
    admin, system
):
    from juya_api.job_models import Job

    from .content_helpers import key, process_jobs

    batch = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "docx"}).json()
    path = f"/api/admin/v1/imports/{batch['id']}/files"
    uploaded = admin.post(
        path + "?kind=docx",
        headers=key(),
        files={"file": ("one.docx", document("保留原文件"), "application/octet-stream")},
    ).json()
    with system["admin"].app.state.sessions.begin() as db:
        job = db.get(Job, uploaded["job_id"])
        job.state, job.error_code = "failed", "worker_interrupted"
    headers = key()
    response = admin.post(path + f"/{uploaded['id']}/retry", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["id"] == uploaded["id"]
    assert response.json()["job_id"] != uploaded["job_id"]
    assert admin.post(path + f"/{uploaded['id']}/retry", headers=headers).json() == response.json()
    process_jobs(admin)
    result = admin.get(f"/api/admin/v1/imports/{batch['id']}").json()
    assert len(result["items"]) == 1 and result["files"][0]["state"] == "ready"
    assert admin.post(path + "/unknown/retry", headers=key()).status_code == 404


def test_oversized_child_asset_does_not_discard_recoverable_text_or_other_zip_folders(
    admin, system
):
    import os

    from .content_helpers import key, picture, process_jobs, recording

    system["settings"].image_limit_mb = 1
    batch = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()
    package = archive(
        [
            ("bad-image/内容.docx", document("缺图可恢复")),
            ("bad-image/场景图.png", os.urandom(1_100_000)),
            ("good/内容.docx", document("独立完整")),
            ("good/场景图.png", picture()),
            ("good/完整音频.wav", recording()),
        ]
    )
    response = admin.post(
        f"/api/admin/v1/imports/{batch['id']}/files?kind=zip",
        headers=key(),
        files={"file": ("mixed.zip", package, "application/zip")},
    )
    assert response.status_code == 201, response.text
    process_jobs(admin)
    result = admin.get(f"/api/admin/v1/imports/{batch['id']}").json()
    assert [item["state"] for item in result["items"]] == ["incomplete", "ready"]
    assert result["items"][0]["content"]["dialogue"]
    failed = [file for file in result["files"] if file["state"] == "failed"]
    assert len(failed) == 1 and failed[0]["name"] == "bad-image/场景图.png"
    assert failed[0]["error_code"] == "archive_member_limit"
    assert next(file for file in result["files"] if not file["parent_id"])["state"] == "ready"
