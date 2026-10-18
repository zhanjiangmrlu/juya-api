from .content_helpers import draft, key, picture, process_jobs, publish


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
