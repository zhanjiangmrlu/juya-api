"""Real image bytes pin the upload boundary, transparency and WebP quality floor."""

import hashlib
import io
import os
import random

import pytest
from PIL import Image

from .content_helpers import key, picture, process_jobs


def noisy_image(mode="RGB", size=(1600, 1600)):
    """Build deterministic high entropy input requiring meaningful compression."""
    image = Image.frombytes(mode, size, random.Random(17).randbytes(size[0] * size[1] * len(mode)))
    if mode == "RGBA":
        image.paste((255, 0, 0, 0), (0, 0, 400, 400))
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


@pytest.mark.parametrize("length", [1048575, 1048576])
def test_at_or_below_threshold_is_byte_identical(length):
    from juya_api.image_processing import normalize_admin_image

    raw = picture().ljust(length, b"\0")
    assert normalize_admin_image(raw) == raw


@pytest.mark.parametrize("mode", ["RGB", "RGBA"])
def test_large_image_is_real_bounded_webp_with_quality_at_least_80(mode, monkeypatch):
    from juya_api.image_processing import normalize_admin_image

    raw = noisy_image(mode)
    save = Image.Image.save
    qualities = []

    def record_save(image, target, format=None, **options):
        if format == "WEBP":
            qualities.append(options["quality"])
        return save(image, target, format, **options)

    monkeypatch.setattr(Image.Image, "save", record_save)
    result = normalize_admin_image(raw)
    assert len(result) <= 1048576
    assert min(qualities) >= 80
    with Image.open(io.BytesIO(result)) as image:
        assert image.format == "WEBP"
        assert image.width < 1600
        assert image.width == image.height
        if mode == "RGBA":
            assert image.mode == "RGBA"
            assert image.getchannel("A").getextrema() == (0, 255)
    assert normalize_admin_image(result) == result


def test_exif_orientation_applied_before_metadata_removed():
    from juya_api.image_processing import normalize_admin_image

    image = Image.new("RGB", (160, 80), "red")
    exif = Image.Exif()
    exif[274] = 6
    output = io.BytesIO()
    image.save(output, "JPEG", exif=exif)
    result = normalize_admin_image(output.getvalue().ljust(1048577, b"\0"))
    with Image.open(io.BytesIO(result)) as oriented:
        assert oriented.size == (80, 160)
        assert not oriented.getexif()


def test_large_corrupt_image_rejected():
    from juya_api.errors import DomainError
    from juya_api.image_processing import normalize_admin_image

    with pytest.raises(DomainError) as error:
        normalize_admin_image(random.Random(99).randbytes(1200000))
    assert error.value.code == "image_invalid"


@pytest.mark.parametrize("domain", ["scene", "listening"])
def test_single_upload_stores_webp_but_retains_source_identity(admin, system, domain):
    from juya_api.content_models import Media
    from juya_api.storage import ObjectStorage

    raw = noisy_image(size=(1000, 1000))
    if domain == "scene":
        path = "/api/admin/v1/media?kind=image"
    else:
        from .test_listening import A, post, topic

        row = post(admin, A + "/articles", {"category_id": topic(admin)["id"], "payload": {}})
        path = A + f"/articles/{row['id']}/media?kind=image"
    operation = key()
    response = admin.post(path, headers=operation, files={"file": ("图片.png", raw, "image/png")})
    assert response.status_code in {200, 201}, response.text
    media_id = response.json()["id"]
    process_jobs(admin)
    with system["sessions"]() as db:
        medium = db.get(Media, media_id)
        assert medium.content_type == "image/webp"
        assert medium.size <= 1048576
        assert medium.source_sha256 == hashlib.sha256(raw).hexdigest()
        stored = ObjectStorage(system["settings"]).read(medium.storage_key)
        assert medium.sha256 == hashlib.sha256(stored).hexdigest()
        assert medium.size == len(stored)
    retry = admin.post(path, headers=operation, files={"file": ("图片.png", raw, "image/png")})
    assert retry.json()["id"] == media_id


@pytest.mark.parametrize("domain", ["scene", "listening"])
@pytest.mark.parametrize("mode", ["zip", "docx"])
def test_import_images_are_normalized_and_cross_package_duplicates_stay_duplicates(
    admin, system, domain, mode
):
    from sqlalchemy import select

    from juya_api.content_models import Media
    from juya_api.storage import ObjectStorage

    from .test_imports import archive
    from .test_imports import document as scene_document
    from .test_listening import A, post
    from .test_listening_imports import document as listening_document

    raw = noisy_image(size=(1000, 1000))
    doc = scene_document("同一张卡") if domain == "scene" else listening_document("同一篇文章")
    if domain == "scene":
        batch = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": mode}).json()
        path = f"/api/admin/v1/imports/{batch['id']}/files"
        entries = [("资料/内容.docx", doc), ("资料/图片.png", raw)]
        files = (
            [("one.zip", archive(entries), "zip")]
            if mode == "zip"
            else [("内容.docx", doc, "docx"), ("同一张卡.png", raw, "image")]
        )
        for name, data, kind in files:
            result = admin.post(path + f"?kind={kind}", headers=key(), files={"file": (name, data)})
            assert result.status_code == 201, result.text
        process_jobs(admin)
        result = admin.get(f"/api/admin/v1/imports/{batch['id']}").json()
        if mode == "docx":
            resolved = admin.post(f"/api/admin/v1/imports/{batch['id']}/resolve", headers=key())
            assert resolved.status_code == 200, resolved.text
            result = resolved.json()
        image_file = next(f for f in result["files"] if f["kind"] == "image")
        assert image_file["state"] == "ready", result
        assert result["items"][0]["content"]["image_id"] == image_file["media_id"]
        assert image_file["name"].endswith("图片.png" if mode == "zip" else "同一张卡.png")
        # Standalone companion retransmission uses source bytes, not transformed digest.
        if mode == "docx":
            retry = admin.post(
                path + "?kind=image", headers=key(), files={"file": ("同一张卡.png", raw)}
            )
            assert retry.json()["id"] == image_file["id"]
    else:
        batch = post(admin, A + "/imports", {"mode": mode})
        entries = [("资料/内容.docx", doc), ("资料/图片.png", raw)]
        files = (
            [("files", ("one.zip", archive(entries)))]
            if mode == "zip"
            else [("files", ("内容.docx", doc)), ("files", ("图片.png", raw))]
        )
        result = admin.post(
            A + f"/imports/{batch['id']}/files?revision={batch['revision']}",
            headers=key(),
            files=files,
        )
        assert result.status_code == 200, result.text
        assert result.json()["candidates"][0]["payload"]["image_id"]
        # The next identical package must reuse its immutable image input.
        batch = result.json()
        result = admin.post(
            A + f"/imports/{batch['id']}/files?revision={batch['revision']}",
            headers=key(),
            files=files,
        )
        assert result.status_code == 200, result.text
        assert result.json()["counts"]["duplicate"] == 1
    with system["sessions"]() as db:
        images = list(db.scalars(select(Media).where(Media.kind == "image")))
        assert len(images) == 1
        medium = images[0]
        assert medium.source_sha256 == hashlib.sha256(raw).hexdigest()
        stored = ObjectStorage(system["settings"]).read(medium.storage_key)
        assert len(stored) == medium.size <= 1048576
        assert hashlib.sha256(stored).hexdigest() == medium.sha256
        assert Image.open(io.BytesIO(stored)).format == "WEBP"


@pytest.mark.parametrize("backend", ["sqlite", pytest.param("mysql", marks=pytest.mark.mysql)])
def test_0030_preserves_existing_media_and_matches_model(tmp_path, monkeypatch, backend):
    from alembic import command
    from sqlalchemy import MetaData, create_engine, inspect, text

    from .test_import_recovery_migrations import migration_config

    url = (
        os.getenv("JUYA_TEST_DATABASE_URL")
        if backend == "mysql"
        else f"sqlite:///{tmp_path / 'migration.db'}"
    )
    if not url:
        pytest.skip("Dedicated MySQL required")
    engine = create_engine(url, hide_parameters=True)
    if backend == "mysql":
        assert engine.url.database == "juya_verify" and engine.url.host == "localhost"
        metadata = MetaData()
        metadata.reflect(engine)
        metadata.drop_all(engine)
    config = migration_config(monkeypatch, url)
    command.upgrade(config, "0029")
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO media "
                "(id,owner_kind,owner_id,kind,state,storage_key,"
                "content_type,size,sha256,created_at) "
                "VALUES ('old','admin','admin','image','ready','old/key','image/png',"
                "99,'oldhash','2026-11-17 00:00:00')"
            )
        )
        before = db.execute(text("SELECT * FROM media")).one()
    command.upgrade(config, "head")
    assert "source_sha256" in {c["name"] for c in inspect(engine).get_columns("media")}
    with engine.connect() as db:
        after = db.execute(text("SELECT * FROM media")).one()
        assert tuple(after[:-1]) == tuple(before)
        assert after[-1] is None
    command.check(config)
    engine.dispose()


def test_large_webp_is_recompressed_and_invalid_animated_input_rejected():
    from juya_api.errors import DomainError
    from juya_api.image_processing import normalize_admin_image

    image = Image.open(io.BytesIO(noisy_image()))
    output = io.BytesIO()
    image.save(output, "WEBP", lossless=True)
    assert len(output.getvalue()) > 1048576
    assert len(normalize_admin_image(output.getvalue())) <= 1048576
    animation = io.BytesIO()
    image.save(
        animation,
        "WEBP",
        save_all=True,
        append_images=[Image.new("RGB", image.size)],
        lossless=True,
        duration=100,
    )
    with pytest.raises(DomainError):
        normalize_admin_image(animation.getvalue())


def test_scene_zip_bad_image_does_not_discard_good_sibling(admin):
    from .test_imports import archive, document

    batch = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()
    entries = [
        ("good/内容.docx", document("好图")),
        ("good/图片.png", noisy_image(size=(1000, 1000))),
        ("bad/内容.docx", document("坏图")),
        ("bad/图片.png", random.Random(99).randbytes(1200000)),
    ]
    response = admin.post(
        f"/api/admin/v1/imports/{batch['id']}/files?kind=zip",
        headers=key(),
        files={"file": ("mixed.zip", archive(entries))},
    )
    assert response.status_code == 201
    process_jobs(admin)
    result = admin.get(f"/api/admin/v1/imports/{batch['id']}").json()
    images = [f for f in result["files"] if f["kind"] == "image"]
    assert {f["state"] for f in images} == {"ready", "failed"}
    assert next(f for f in images if f["state"] == "failed")["error_code"] == "image_invalid"


def test_source_hash_preserves_legacy_semantic_identity(admin, system):
    from juya_api.content_models import Media
    from juya_api.image_processing import media_source_hash
    from juya_api.import_service import content_hash
    from juya_api.listening_imports import source_hash

    from .content_helpers import draft

    card = draft(admin)
    raw = noisy_image(size=(1000, 1000))
    uploaded = admin.post(
        "/api/admin/v1/media?kind=image", headers=key(), files={"file": ("new.png", raw)}
    )
    with system["sessions"].begin() as db:
        medium = db.get(Media, uploaded.json()["id"])
        old = db.get(Media, card["content"]["image_id"])
        old.sha256 = hashlib.sha256(raw).hexdigest()
        old.source_sha256 = None
        assert media_source_hash(old) == media_source_hash(medium)
        assert content_hash(db, card["content"]) == content_hash(
            db, {**card["content"], "image_id": medium.id}
        )
        assert source_hash(db, {"image_id": old.id}) == source_hash(db, {"image_id": medium.id})


def test_scene_large_image_duplicate_across_distinct_archives(admin):
    from .test_imports import archive, document

    batch = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()
    entries = [
        ("same/内容.docx", document("相同内容")),
        ("same/图片.png", noisy_image(size=(1000, 1000))),
    ]
    for index in range(2):
        package = archive(entries + [(f"ignored{index}.txt", b"distinct package")])
        response = admin.post(
            f"/api/admin/v1/imports/{batch['id']}/files?kind=zip",
            headers=key(),
            files={"file": (f"{index}.zip", package)},
        )
        assert response.status_code == 201
        process_jobs(admin)
    result = admin.get(f"/api/admin/v1/imports/{batch['id']}").json()
    assert len(result["items"]) == 2
    duplicates = [item for item in result["items"] if item["state"] == "duplicate"]
    assert len(duplicates) == 1
    detail = admin.get(f"/api/admin/v1/imports/{batch['id']}/duplicates").json()
    assert detail["items"][0]["reason"] == "cross_package"


def test_saved_legacy_scene_reimport_keeps_original_image_identity(admin, system):
    from juya_api.content_models import Media
    from juya_api.storage import ObjectStorage

    from .content_helpers import recording
    from .test_imports import archive, document

    raw = noisy_image(size=(1000, 1000))
    package = archive(
        [
            ("same/内容.docx", document("已保存图", content_type="配图词汇")),
            ("same/图片.png", raw),
            ("same/完整音频.wav", recording()),
        ]
    )
    batches = []
    for number in range(2):
        batch = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": "zip"}).json()
        batches.append(batch)
        response = admin.post(
            f"/api/admin/v1/imports/{batch['id']}/files?kind=zip",
            headers=key(),
            files={"file": ("same.zip", package)},
        )
        assert response.status_code == 201
        process_jobs(admin)
        route = f"/api/admin/v1/imports/{batch['id']}"
        result = admin.get(route).json()
        if number == 0:
            confirmation = admin.get(route + "/confirmation").json()
            saved = admin.post(
                route + "/save",
                headers=key(),
                json={"confirmed": True, "version": confirmation["version"]},
            )
            assert saved.status_code == 200, saved.text
            process_jobs(admin)
            assert admin.get("/api/admin/v1/cards").json()["total"] == 1
            image_id = result["items"][0]["content"]["image_id"]
            # Represent pre-feature media, whose original bytes and hash were stored unchanged.
            with system["sessions"].begin() as db:
                medium = db.get(Media, image_id)
                medium.source_sha256 = None
                medium.sha256 = hashlib.sha256(raw).hexdigest()
                medium.size = len(raw)
                medium.storage_key = "legacy/source-image"
                medium.content_type = "image/png"
                ObjectStorage(system["settings"]).put(medium.storage_key, raw, "image/png")
        else:
            assert result["items"][0]["state"] == "duplicate", result
            detail = admin.get(route + "/duplicates").json()["items"][0]
            assert detail["reason"] == "existing_content"
            assert admin.get("/api/admin/v1/cards").json()["total"] == 1
