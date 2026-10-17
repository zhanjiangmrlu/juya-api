from .content_helpers import draft, key, picture, publish


def test_real_image_is_decoded_and_thumbnail_generated(admin):
    response = admin.post(
        "/api/admin/v1/media?kind=image",
        headers=key(),
        files={"file": ("scene.png", picture(), "image/png")},
    )
    assert response.status_code == 201
    image = response.json()
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
    assert response.status_code == 422


def test_audio_ticket_streams_ranges_and_is_revoked_by_offline(admin, mini):
    card = draft(admin)
    version = publish(admin, card)["current_version_id"]
    audio_id = card["content"]["audio_id"]
    ticket = mini.get(f"/api/mini/v1/cards/{card['id']}/media/{audio_id}/url?version_id={version}")
    assert ticket.status_code == 200
    url = ticket.json()["url"]
    audio = mini.get(url, headers={"Range": "bytes=0-15"})
    assert audio.status_code == 206
    assert audio.content[:4] == b"RIFF"
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
