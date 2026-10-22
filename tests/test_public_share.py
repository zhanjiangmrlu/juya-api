"""Anonymous shares expose only revocable current titles and bounded image copies."""

import hashlib
import io

import pytest
from PIL import Image
from sqlalchemy import func, select

from .content_helpers import content, draft, picture, publish

PUBLIC = "/api/mini/v1/public/cards/"


@pytest.fixture
def share_scene(admin, system):
    card = publish(admin, draft(admin))
    return system["mini"], card


def test_anonymous_summary_is_a_current_public_whitelist_and_private_routes_stay_private(
    share_scene, system
):
    from juya_api.content_models import Operation
    from juya_api.discovery_models import ReadingStart
    from juya_api.learning_models import Completion
    from juya_api.models import User

    client, card = share_scene
    with system["sessions"]() as db:
        before = [
            db.scalar(select(func.count()).select_from(model))
            for model in [User, ReadingStart, Completion, Operation]
        ]
    response = client.get(PUBLIC + card["id"] + "/share")
    assert response.status_code == 200, response.text
    value = response.json()
    assert set(value) == {"card_id", "version_id", "name", "title_en", "images"}
    assert value["card_id"] == card["id"]
    assert value["version_id"] == card["current_version_id"]
    assert value["name"] == "在咖啡店点单" and value["title_en"] == "Ordering Coffee"
    assert set(value["images"]) == {"friends", "timeline"}
    for variant, dimensions in [("friends", (600, 480)), ("timeline", (600, 600))]:
        image = value["images"][variant]
        assert set(image) == {"url", "width", "height"}
        assert (image["width"], image["height"]) == dimensions
        result = client.get(image["url"])
        assert result.status_code == 200
        assert result.headers["Content-Type"] == "image/jpeg"
    assert client.get("/api/mini/v1/cards/" + card["id"]).status_code == 401
    assert client.get("/api/mini/v1/me").status_code == 401
    with system["sessions"]() as db:
        assert [
            db.scalar(select(func.count()).select_from(model))
            for model in [User, ReadingStart, Completion, Operation]
        ] == before


@pytest.mark.parametrize("missing_english", [None, "", " ", "absent"])
def test_drafts_stay_private_and_historical_missing_english_is_not_fabricated(
    admin, system, missing_english
):
    from juya_api.content_models import CardDraft, CardVersion

    candidate = draft(admin)
    client = system["mini"]
    assert client.get(PUBLIC + candidate["id"] + "/share").status_code == 410
    card = publish(admin, candidate)
    with system["sessions"].begin() as db:
        version = db.get(CardVersion, card["current_version_id"])
        version.payload = {
            key: value for key, value in version.payload.items() if key != "title_en"
        }
        if missing_english != "absent":
            version.payload = version.payload | {"title_en": missing_english}
        candidate = db.get(CardDraft, card["id"])
        candidate.payload = candidate.payload | {
            "name": "私有草稿标题",
            "title_en": "Private draft",
        }
    response = client.get(PUBLIC + card["id"] + "/share")
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "在咖啡店点单"
    assert response.json()["title_en"] == ""
    assert "Private draft" not in response.text and "私有草稿" not in response.text


def test_covers_contain_the_complete_oriented_picture_strip_metadata_and_preserve_original(
    admin, system
):
    from juya_api.content_models import Media
    from juya_api.storage import ObjectStorage

    image = Image.new("RGB", (80, 160), "#0066cc")
    for point, color in [
        ((0, 0), "red"),
        ((0, 140), "green"),
        ((60, 0), "yellow"),
        ((60, 140), "magenta"),
    ]:
        image.paste(color, (*point, point[0] + 20, point[1] + 20))
    exif = Image.Exif()
    exif[274], exif[270] = 6, "private camera metadata"
    original = io.BytesIO()
    image.save(original, "JPEG", exif=exif, quality=100, subsampling=0)
    upload = admin.post(
        "/api/admin/v1/media?kind=image",
        files={"file": ("source.jpg", original.getvalue(), "image/jpeg")},
        headers={"Idempotency-Key": "public-share-oriented-image-0001"},
    )
    assert upload.status_code == 201, upload.text
    payload = content(admin) | {"image_id": upload.json()["id"]}
    card = publish(admin, draft(admin, payload))
    client, storage = system["mini"], ObjectStorage(system["settings"])
    with system["sessions"]() as db:
        medium = db.get(Media, upload.json()["id"])
        source_key, source_digest = medium.storage_key, medium.sha256
    shared = client.get(PUBLIC + card["id"] + "/share")
    assert shared.status_code == 200, shared.text
    for variant, size, top in [("friends", (600, 480), 90), ("timeline", (600, 600), 150)]:
        url = shared.json()["images"][variant]["url"]
        response = client.get(url)
        derived = Image.open(io.BytesIO(response.content))
        assert derived.format == "JPEG" and derived.size == size
        assert not derived.getexif() and b"private camera metadata" not in response.content
        # EXIF rotates 80x160 to 160x80. All four 20px corner patches survive
        # within the 600x300 contained picture, with padding above and below.
        for point, expected in [
            ((30, top + 30), (0, 128, 0)),
            ((570, top + 30), (255, 0, 0)),
            ((30, top + 270), (255, 0, 255)),
            ((570, top + 270), (255, 255, 0)),
        ]:
            assert (
                max(
                    abs(actual - wanted)
                    for actual, wanted in zip(derived.getpixel(point), expected, strict=True)
                )
                < 35
            )
        assert min(derived.getpixel((300, 5))) > 235
        head = client.head(url)
        assert head.status_code == 200 and head.content == b""
        assert int(head.headers["Content-Length"]) == len(response.content)
        assert head.headers["Cache-Control"] == "no-store"
        assert head.headers["X-Content-Type-Options"] == "nosniff"
    assert storage.read(source_key) == original.getvalue()
    assert hashlib.sha256(storage.read(source_key)).hexdigest() == source_digest


@pytest.mark.parametrize("method", ["get", "head"])
@pytest.mark.parametrize(
    "change, expected",
    [
        ("offline", 410),
        ("deleted", 410),
        ("version", 409),
        ("not_ready", 503),
        ("missing_medium", 503),
        ("missing_object", 503),
        ("corrupt_object", 503),
    ],
)
def test_warm_cover_rechecks_publish_version_and_source_for_every_request(
    share_scene, system, method, change, expected
):
    from juya_api.content_models import Card, CardVersion, Media
    from juya_api.storage import ObjectStorage

    client, card = share_scene
    summary = client.get(PUBLIC + card["id"] + "/share")
    assert summary.status_code == 200, summary.text
    url = summary.json()["images"]["friends"]["url"]
    assert client.get(url).status_code == 200
    with system["sessions"].begin() as db:
        row = db.get(Card, card["id"])
        version = db.get(CardVersion, row.current_version_id)
        medium = db.get(Media, version.payload["image_id"])
        if change == "offline":
            row.status = "offline"
        elif change == "deleted":
            row.deleted_at = client.app.state.clock()
        elif change == "version":
            db.add(
                CardVersion(
                    id="new-published-version",
                    card_id=row.id,
                    number=2,
                    payload=version.payload,
                    content_hash="new-content",
                    published_at=client.app.state.clock(),
                )
            )
            row.current_version_id = "new-published-version"
        elif change == "not_ready":
            medium.state = "failed"
        elif change == "missing_medium":
            version.payload = version.payload | {"image_id": "missing-image"}
        elif change == "missing_object":
            ObjectStorage(system["settings"]).path(medium.storage_key).unlink()
        else:
            ObjectStorage(system["settings"]).put(
                medium.storage_key, b"x" * medium.size, medium.content_type
            )
    response = getattr(client, method)(url, headers={"If-None-Match": "*", "Range": "bytes=0-0"})
    assert response.status_code == expected, response.text
    if change not in {"offline", "deleted", "version"}:
        unavailable = client.get(PUBLIC + card["id"] + "/share")
        assert unavailable.status_code == 503
        assert unavailable.json()["error"]["code"] == "share_image_unavailable"


@pytest.mark.parametrize("kind", ["unrecognized", "bad_crc"])
def test_real_decode_rejects_invalid_source_even_when_metadata_digest_matches(
    share_scene, system, kind
):
    from juya_api.content_models import CardVersion, Media
    from juya_api.storage import ObjectStorage

    client, card = share_scene
    with system["sessions"].begin() as db:
        version = db.get(CardVersion, card["current_version_id"])
        medium = db.get(Media, version.payload["image_id"])
        data = b"not an image"
        if kind == "bad_crc":
            broken = bytearray(picture())
            start = broken.index(b"IDAT")
            checksum = start + 4 + int.from_bytes(broken[start - 4 : start], "big")
            broken[checksum : checksum + 4] = b"\0\0\0\0"
            data = bytes(broken)
        medium.size, medium.sha256 = len(data), hashlib.sha256(data).hexdigest()
        ObjectStorage(system["settings"]).put(medium.storage_key, data, medium.content_type)
    response = client.get(PUBLIC + card["id"] + "/share")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "share_image_unavailable"


def test_unrecognized_variant_or_unknown_card_never_opens_arbitrary_media(share_scene):
    client, card = share_scene
    value = client.get(PUBLIC + card["id"] + "/share").json()
    assert client.get(PUBLIC + "missing-card/share").status_code == 404
    path = PUBLIC + card["id"] + "/share/images/" + value["version_id"] + "/original"
    assert client.get(path).status_code == 422
    assert client.head(path).status_code == 422


@pytest.mark.mysql
@pytest.mark.parametrize("method", ["get", "head"])
def test_real_mysql_public_image_rechecks_a_publication_disabled_during_source_io(
    share_scene, system, monkeypatch, method
):
    if system["engine"].dialect.name != "mysql":
        pytest.skip("Real MySQL READ COMMITTED share revocation during source IO")
    from juya_api.content_models import Card

    client, card = share_scene
    summary = client.get(PUBLIC + card["id"] + "/share")
    assert summary.status_code == 200, summary.text
    prepare = client.app.state.share_images.prepare

    def disabled_after_preparing(*args):
        result = prepare(*args)
        with system["sessions"].begin() as writer:
            writer.get(Card, card["id"]).status = "offline"
        return result

    monkeypatch.setattr(client.app.state.share_images, "prepare", disabled_after_preparing)
    assert getattr(client, method)(summary.json()["images"]["friends"]["url"]).status_code == 410
