"""Unmarked UTF-8 ZIP names stay readable without changing member lookup or identity."""

import zipfile

import pytest

from .content_helpers import key, picture, process_jobs, recording
from .test_imports import archive, document


class UnmarkedUTF8Info(zipfile.ZipInfo):
    """Reproduce macOS archives whose UTF-8 name bytes omit the language flag."""

    def _encodeFilenameFlags(self):
        return self.filename.encode("utf-8"), self.flag_bits & ~0x800


def unmarked_archive(entries):
    """Write entries with real unmarked UTF-8 local and central directory names."""
    return archive([(UnmarkedUTF8Info(name), body) for name, body in entries])


@pytest.mark.parametrize("unmarked", [False, True])
def test_zip_decodes_names_without_breaking_member_reads(unmarked):
    from juya_api.import_parser import checked_archive, member_bytes

    entries = [("资料/场景图.png", b"image"), ("资料/Choosing a Play.wav", b"audio")]
    data = unmarked_archive(entries) if unmarked else archive(entries)
    with checked_archive(data) as package:
        # Original names must still match local headers when reading a member.
        for member, (_, body) in zip(package.infolist(), entries, strict=True):
            assert member_bytes(package, member.filename, 100) == body


@pytest.mark.parametrize("legacy", [False, True])
def test_zip_names_are_readable_in_review_results_and_saved_media(admin, system, legacy):
    from juya_api.import_models import ImportFile

    batch_id = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()["id"]
    folder = "后台导入资料-含音标-20261017/为戏剧社挑一个剧本"
    names = [
        f"{folder}/内容.docx",
        f"{folder}/场景图.png",
        f"{folder}/Choosing a Play for Drama Club.wav",
    ]
    response = admin.post(
        f"/api/admin/v1/imports/{batch_id}/files?kind=zip",
        headers=key(),
        files={
            "file": (
                "后台导入资料.zip",
                unmarked_archive(
                    list(
                        zip(
                            names,
                            [document("为戏剧社挑一个剧本"), picture(), recording()],
                            strict=True,
                        )
                    )
                ),
                "application/zip",
            )
        },
    )
    assert response.status_code == 201, response.text
    process_jobs(admin)
    root_id = response.json()["id"]
    if legacy:
        # Model records already persisted by the old CP437-only importer.
        with system["sessions"].begin() as db:
            from sqlalchemy import select

            children = db.scalars(select(ImportFile).where(ImportFile.parent_id == root_id)).all()
            for child in children:
                if child.name in names:
                    child.name = child.name.encode("utf-8").decode("cp437")
            from juya_api.job_models import Job

            root = db.get(ImportFile, root_id)
            job = db.get(Job, root.job_id)
            job.result = {k: v for k, v in job.result.items() if k != "filename_encoding"}
    result = admin.get(f"/api/admin/v1/imports/{batch_id}").json()
    assert {f["name"] for f in result["files"] if f["parent_id"]} == set(names)
    item = result["items"][0]
    assert item["source_folder"] == folder
    assert item["source_zip_name"] == "后台导入资料.zip"
    assert item["content"]["dialogue"][0]["english"] == "Could I get a latte, please?"
    assert item["state"] == "ready"
    if legacy:
        # A replay must normalize old rows before recording the new parser receipt.
        ids = {file["id"] for file in result["files"]}
        with system["sessions"].begin() as db:
            root = db.get(ImportFile, root_id)
            job = db.get(Job, root.job_id)
            job.state = "queued"
        process_jobs(admin)
        replayed = admin.get(f"/api/admin/v1/imports/{batch_id}").json()
        assert {file["id"] for file in replayed["files"]} == ids
        assert {f["name"] for f in replayed["files"] if f["parent_id"]} == set(names)
        assert len(replayed["items"]) == 1
    confirmation = admin.get(f"/api/admin/v1/imports/{batch_id}/confirmation").json()
    saved = admin.post(
        f"/api/admin/v1/imports/{batch_id}/save",
        headers=key(),
        json={"confirmed": True, "version": confirmation["version"]},
    )
    assert saved.status_code == 200, saved.text
    process_jobs(admin)
    result = admin.get(f"/api/admin/v1/imports/{batch_id}").json()
    assert result["items"][0]["state"] == "saved"
    assert result["items"][0]["source_folder"] == folder
    for field, expected in [("image_id", names[1]), ("audio_id", names[2])]:
        media_id = item["content"][field]
        status = admin.get(f"/api/admin/v1/media/{media_id}/status").json()
        assert status["original_name"] == expected
        assert status["state"] == "ready"


@pytest.mark.parametrize("readable", [False, True])
def test_explicit_utf8_names_are_not_decoded_twice(admin, readable):
    batch_id = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()["id"]
    entries = [
        ("caf├⌐/content.docx", document("保留原名") if readable else b"invalid docx"),
        ("caf├⌐/caf├⌐.png", picture()),
        ("caf├⌐/caf├⌐.wav", recording()),
    ]
    response = admin.post(
        f"/api/admin/v1/imports/{batch_id}/files?kind=zip",
        headers=key(),
        files={"file": ("explicit.zip", archive(entries), "application/zip")},
    )
    assert response.status_code == 201, response.text
    process_jobs(admin)
    result = admin.get(f"/api/admin/v1/imports/{batch_id}").json()
    assert {f["name"] for f in result["files"] if f["parent_id"]} == {n for n, _ in entries}
    item = result["items"][0]
    assert item["source_folder"] == "caf├⌐"
    assert item["content"]["name"] == ("保留原名" if readable else "caf├⌐")
    for file in result["files"]:
        if file["media_id"]:
            status = admin.get(f"/api/admin/v1/media/{file['media_id']}/status").json()
            assert status["original_name"] == file["name"]


def test_zip_rejects_paths_that_collide_after_decoding():
    from juya_api.errors import DomainError
    from juya_api.import_parser import checked_archive

    entries = [
        (UnmarkedUTF8Info("资料/内容.docx"), b"one"),
        ("资料/内容.docx", b"two"),
    ]
    with (
        pytest.warns(UserWarning, match="Duplicate name"),
        pytest.raises(DomainError, match="archive_unsafe"),
    ):
        checked_archive(archive(entries))


def test_zip_preserves_ascii_and_legacy_western_names():
    from juya_api.import_parser import checked_archive, member_bytes

    class WesternInfo(zipfile.ZipInfo):
        def _encodeFilenameFlags(self):
            return self.filename.encode("cp437"), self.flag_bits & ~0x800

    with checked_archive(archive([(WesternInfo("café/Play.wav"), b"audio")])) as package:
        assert package.namelist() == ["café/Play.wav"]
        assert member_bytes(package, "café/Play.wav", 100) == b"audio"
