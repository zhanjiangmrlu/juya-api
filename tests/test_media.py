from .content_helpers import draft, key, picture, process_jobs, publish


def test_detail_exposes_readable_published_thumbnail_despite_a_new_candidate(admin, mini):
    """The detail's small image must reference the publication's derivative, not its original."""
    card = draft(admin)
    published = publish(admin, card)
    image = admin.get(f"/api/admin/v1/media/{card['content']['image_id']}/status").json()
    candidate = draft(admin)
    changed = admin.put(
        f"/api/admin/v1/cards/{card['id']}",
        headers=key(),
        json={"revision": 1, "content": candidate["content"]},
    )
    assert changed.status_code == 200, changed.text
    response = mini.get(f"/api/mini/v1/cards/{card['id']}")
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["thumbnail_id"] == image["thumbnail_id"]
    assert detail["thumbnail_id"] != detail["content"]["image_id"]
    assert detail["version_id"] == published["current_version_id"]
    ticket = mini.get(
        f"/api/mini/v1/cards/{card['id']}/media/{detail['thumbnail_id']}/url",
        params={"version_id": detail["version_id"]},
    )
    assert ticket.status_code == 200, ticket.text
    small = mini.get(ticket.json()["url"])
    assert small.status_code == 200
    assert small.headers["content-type"] == "image/webp"


def test_real_image_is_decoded_and_thumbnail_generated(admin):
    response = admin.post(
        "/api/admin/v1/media?kind=image",
        headers=key(),
        files={"file": ("scene.png", picture(), "image/png")},
    )
    assert response.status_code == 201
    image = response.json()
    assert image["state"] == "processing"
    assert image["width"] is None
    assert admin.get(f"/api/admin/v1/media/{image['id']}").status_code == 404
    process_jobs(admin)
    image = admin.get(f"/api/admin/v1/media/{image['id']}/status").json()
    assert image["state"] == "ready"
    assert image["width"] == 120
    assert image["height"] == 80
    assert image["thumbnail_id"] != image["id"]
    assert admin.get(f"/api/admin/v1/media/{image['thumbnail_id']}").status_code == 200


def test_filename_and_mime_are_not_trusted_for_decode(admin):
    response = admin.post(
        "/api/admin/v1/media?kind=image",
        headers=key(),
        files={"file": ("fake.png", b"not an image", "image/png")},
    )
    assert response.status_code == 201
    process_jobs(admin)
    image = admin.get(f"/api/admin/v1/media/{response.json()['id']}/status").json()
    assert image["state"] == "failed"
    assert image["error_code"] == "image_invalid"


def test_audio_ticket_streams_ranges_and_is_revoked_by_offline(admin, mini):
    card = draft(admin)
    version = publish(admin, card)["current_version_id"]
    audio_id = card["content"]["audio_id"]
    ticket = mini.get(f"/api/mini/v1/cards/{card['id']}/media/{audio_id}/url?version_id={version}")
    assert ticket.status_code == 200
    url = ticket.json()["url"]
    audio = mini.get(url, headers={"Range": "bytes=0-15"})
    assert audio.status_code == 206
    assert audio.headers["content-type"] == "audio/mpeg"
    assert not audio.content.startswith(b"RIFF")
    assert len(audio.content) == 16
    assert audio.headers["cache-control"] == "no-store"
    assert (
        admin.post(
            f"/api/admin/v1/cards/{card['id']}/offline", headers=key(), json={"revision": 1}
        ).status_code
        == 200
    )
    assert mini.get(url).status_code == 410


def test_resource_cannot_be_requested_through_an_unrelated_card(admin, mini):
    first = draft(admin)
    second = draft(admin)
    publish(admin, first)
    version = publish(admin, second)["current_version_id"]
    response = mini.get(
        f"/api/mini/v1/cards/{second['id']}/media/{first['content']['audio_id']}/url?version_id={version}"
    )
    assert response.status_code == 404


def test_logout_revokes_previously_issued_media_tickets(admin, mini):
    card = draft(admin)
    version = publish(admin, card)["current_version_id"]
    url = mini.get(
        f"/api/mini/v1/cards/{card['id']}/media/{card['content']['image_id']}/url?version_id={version}"
    ).json()["url"]
    assert mini.post("/api/mini/v1/auth/logout").status_code == 200
    assert mini.get(url).status_code == 401


def test_deleted_history_permits_only_its_safe_thumbnail_not_the_original(admin, mini):
    card = draft(admin)
    version = publish(admin, card)["current_version_id"]
    assert (
        mini.post(
            f"/api/mini/v1/cards/{card['id']}/complete", headers=key(), json={"version_id": version}
        ).status_code
        == 200
    )
    image_id = card["content"]["image_id"]
    thumb = admin.get(f"/api/admin/v1/media/{image_id}/status").json()["thumbnail_id"]
    assert (
        admin.request(
            "DELETE", f"/api/admin/v1/cards/{card['id']}", headers=key(), json={"revision": 1}
        ).status_code
        == 200
    )
    response = mini.get(f"/api/mini/v1/cards/{card['id']}/media/{thumb}/url?purpose=summary")
    assert response.status_code == 200, response.text
    assert mini.get(response.json()["url"]).status_code == 200
    assert (
        mini.get(
            f"/api/mini/v1/cards/{card['id']}/media/{image_id}/url?purpose=summary"
        ).status_code
        == 404
    )


def test_avatar_processing_status_is_scoped_to_its_owner(mini, system):
    from fastapi.testclient import TestClient

    response = mini.post(
        "/api/mini/v1/me/avatar",
        headers=key(),
        files={"file": ("avatar.png", picture(), "image/png")},
    )
    medium = response.json()["id"]
    assert mini.get(f"/api/mini/v1/me/avatar/{medium}/status").json()["state"] == "processing"
    with TestClient(system["mini"].app, base_url="https://testserver") as other:
        login = other.post(
            "/api/mini/v1/auth/wechat",
            headers=key(),
            json={"code": "bob:avatar", "consent": True, "consent_version": "2026-10-17"},
        ).json()
        other.headers["Authorization"] = "Bearer " + login["access_token"]
        assert other.get(f"/api/mini/v1/me/avatar/{medium}/status").status_code == 404
    process_jobs(mini)
    assert mini.get(f"/api/mini/v1/me/avatar/{medium}/status").json()["state"] == "ready"


def test_interrupted_media_can_retry_without_reupload_or_duplicate_jobs(admin, system):
    from juya_api.job_models import Job

    response = admin.post(
        "/api/admin/v1/media?kind=image",
        headers=key(),
        files={"file": ("scene.png", picture(), "image/png")},
    ).json()
    with system["sessions"].begin() as db:
        job = db.get(Job, response["job_id"])
        job.state, job.error_code = "failed", "worker_interrupted"
    headers = key()
    retried = admin.post(f"/api/admin/v1/media/{response['id']}/retry", headers=headers)
    assert retried.status_code == 200, retried.text
    assert retried.json()["id"] == response["id"]
    assert retried.json()["job_id"] != response["job_id"]
    assert (
        admin.post(f"/api/admin/v1/media/{response['id']}/retry", headers=headers).json()
        == retried.json()
    )
    process_jobs(admin)
    assert admin.get(f"/api/admin/v1/media/{response['id']}/status").json()["state"] == "ready"


def test_unfinished_media_cannot_be_saved_as_a_candidate_reference(admin):
    response = admin.post(
        "/api/admin/v1/media?kind=image",
        headers=key(),
        files={"file": ("image.png", picture(), "image/png")},
    ).json()
    rejected = admin.post(
        "/api/admin/v1/cards",
        headers=key(),
        json={"content": {"name": "未准备好的素材", "image_id": response["id"]}},
    )
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["error"]["code"] == "media_processing"
    assert admin.get("/api/admin/v1/cards").json()["total"] == 0


def test_admin_list_thumbnail_parameter_reduces_bytes_without_changing_original(admin, monkeypatch):
    """The list URL returns fewer real bytes; the same original URL stays lossless."""
    import io
    import random

    from PIL import Image

    from juya_api.storage import ObjectStorage

    pixels = random.Random(7).randbytes(1024 * 1536 * 3)
    output = io.BytesIO()
    Image.frombytes("RGB", (1024, 1536), pixels).save(output, "PNG")
    original = output.getvalue()
    uploaded = admin.post(
        "/api/admin/v1/media?kind=image",
        headers=key(),
        files={"file": ("poster.png", original, "image/png")},
    )
    assert uploaded.status_code == 201
    process_jobs(admin)
    image = admin.get(f"/api/admin/v1/media/{uploaded.json()['id']}/status").json()
    path = f"/api/admin/v1/media/{image['thumbnail_id']}"
    regular = admin.get(path)
    small = admin.get(path + "?thumbnail=list")
    assert small.status_code == 200
    assert small.headers["content-type"] == "image/webp"
    with Image.open(io.BytesIO(small.content)) as scaled:
        assert scaled.size == (144, 216)
    assert len(small.content) < len(regular.content) / 4
    assert small.headers["cache-control"] == "no-store"
    assert int(small.headers["content-length"]) == len(small.content)
    calls = []
    previous = ObjectStorage.read

    def storage_read(storage, storage_key):
        calls.append(storage_key)
        return previous(storage, storage_key)

    monkeypatch.setattr(ObjectStorage, "read", storage_read)
    assert admin.get(path + "?thumbnail=list").content == small.content
    assert calls == []  # repeated delivery reuses the app's bounded derivative cache
    head = admin.head(path + "?thumbnail=list")
    assert head.content == b""
    assert int(head.headers["content-length"]) == len(small.content)
    partial = admin.get(path + "?thumbnail=list", headers={"Range": "bytes=0-15"})
    assert partial.status_code == 206
    assert partial.content == small.content[:16]
    assert partial.headers["content-range"] == f"bytes 0-15/{len(small.content)}"
    invalid_range = admin.get(path + "?thumbnail=list", headers={"Range": "bytes=999999-"})
    assert invalid_range.status_code == 416
    assert admin.get(f"/api/admin/v1/media/{image['id']}").content == original
    assert admin.get(path).content == regular.content
    assert admin.get(path + "?thumbnail=unbounded").status_code == 422
    assert admin.get(f"/api/admin/v1/media/{image['id']}?thumbnail=list").status_code == 422
    assert admin.post("/api/admin/v1/auth/logout").status_code == 200
    assert admin.get(path + "?thumbnail=list").status_code == 401


def test_list_thumbnail_keeps_small_image_dimensions(admin):
    """The list derivative must not enlarge a source smaller than its target size."""
    import io

    from PIL import Image

    uploaded = admin.post(
        "/api/admin/v1/media?kind=image",
        headers=key(),
        files={"file": ("small.png", picture(), "image/png")},
    )
    process_jobs(admin)
    metadata = admin.get(f"/api/admin/v1/media/{uploaded.json()['id']}/status").json()
    result = admin.get(f"/api/admin/v1/media/{metadata['thumbnail_id']}?thumbnail=list")
    assert result.status_code == 200
    with Image.open(io.BytesIO(result.content)) as image:
        assert image.size == (120, 80)


def test_list_thumbnail_cache_evicts_old_results():
    """Cross-page reads cannot keep an unbounded set of server-generated images."""
    from types import SimpleNamespace

    from juya_api.list_thumbnails import ListThumbnails

    calls = []

    class Storage:
        def read(self, storage_key):
            calls.append(storage_key)
            return picture()

    cache = ListThumbnails(capacity=2)
    storage = Storage()
    media = [
        SimpleNamespace(storage_key=f"image-{number}", sha256=str(number)) for number in range(3)
    ]
    for medium in media:
        cache.read(medium, storage)
    cache.read(media[1], storage)
    assert calls == ["image-0", "image-1", "image-2"]
    cache.read(media[0], storage)
    assert calls == ["image-0", "image-1", "image-2", "image-0"]
    assert len(cache.images) == 2


def test_mini_thumbnail_parameter_scales_ticketed_image_but_preserves_original(
    admin, mini, monkeypatch
):
    """Compress authorized small images while keeping the original delivery intact."""
    import io
    import random

    from PIL import Image

    from . import content_helpers

    output = io.BytesIO()
    Image.frombytes("RGB", (480, 720), random.Random(11).randbytes(480 * 720 * 3)).save(
        output, "PNG"
    )
    original = output.getvalue()
    monkeypatch.setattr(content_helpers, "picture", lambda: original)
    card = draft(admin)
    version = publish(admin, card)["current_version_id"]
    metadata = admin.get(f"/api/admin/v1/media/{card['content']['image_id']}/status").json()
    image_id = metadata["thumbnail_id"]
    ticket = mini.get(f"/api/mini/v1/cards/{card['id']}/media/{image_id}/url?version_id={version}")
    assert ticket.status_code == 200
    url = ticket.json()["url"] + "?thumbnail=list"
    small = mini.get(url)
    assert small.status_code == 200
    assert small.headers["content-type"] == "image/webp"
    assert small.headers["cache-control"] == "no-store"
    with Image.open(io.BytesIO(small.content)) as image:
        assert image.size == (144, 216)
    regular = mini.get(ticket.json()["url"])
    assert len(small.content) < len(regular.content) / 2
    assert mini.head(url).headers["content-length"] == str(len(small.content))
    assert mini.get(url, headers={"Range": "bytes=0-15"}).content == small.content[:16]
    original_ticket = mini.get(
        f"/api/mini/v1/cards/{card['id']}/media/{card['content']['image_id']}/url?version_id={version}"
    ).json()["url"]
    assert mini.get(original_ticket).content == original
    assert mini.get(original_ticket + "?thumbnail=list").status_code == 422
    assert mini.get(ticket.json()["url"] + "?thumbnail=unbounded").status_code == 422
    assert mini.post("/api/mini/v1/auth/logout").status_code == 200
    assert mini.get(url).status_code == 401  # a cached derivative cannot bypass revoked sessions


def test_mini_historical_thumbnail_compression_preserves_history_scope(admin, mini):
    """Keep offline history thumbnails scoped without exposing their originals."""
    card = draft(admin)
    version = publish(admin, card)["current_version_id"]
    thumbnail_id = admin.get(f"/api/admin/v1/media/{card['content']['image_id']}/status").json()[
        "thumbnail_id"
    ]
    assert (
        mini.put(
            f"/api/mini/v1/cards/{card['id']}/favorite", headers=key(), json={"version_id": version}
        ).status_code
        == 200
    )
    current = (
        mini.get(
            f"/api/mini/v1/cards/{card['id']}/media/{thumbnail_id}/url?version_id={version}"
        ).json()["url"]
        + "?thumbnail=list"
    )
    assert mini.get(current).status_code == 200
    assert (
        admin.post(
            f"/api/admin/v1/cards/{card['id']}/offline", headers=key(), json={"revision": 1}
        ).status_code
        == 200
    )
    assert mini.get(current).status_code == 410
    history = mini.get(f"/api/mini/v1/cards/{card['id']}/media/{thumbnail_id}/url?purpose=summary")
    assert history.status_code == 200
    url = history.json()["url"] + "?thumbnail=list"
    assert mini.get(url).status_code == 200
    forbidden = mini.get(
        f"/api/mini/v1/cards/{card['id']}/media/{card['content']['image_id']}/url?purpose=summary"
    )
    assert forbidden.status_code == 404
    assert mini.delete(f"/api/mini/v1/favorites/{card['id']}", headers=key()).status_code == 200
    assert mini.get(url).status_code == 404  # the shared derivative cache cannot retain permission
