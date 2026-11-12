"""CHG0042 protects audio/PDF without closing free text and published pictures."""

import json
from datetime import UTC, timedelta

import pytest
from sqlalchemy import func, select

from juya_api.database import Base
from juya_api.security import encrypt
from tests.content_helpers import draft, key, picture, process_jobs, publish
from tests.test_guest_content import P, set_free
from tests.test_listening import M, article, policy
from tests.test_listening import publish as publish_article
from tests.test_study_notes import save_note, upload


def legacy_public(system, domain, identifier, version, purpose, **references):
    """Seal an exact pre-CHG0042 grant independently of the current issuer."""
    data = {
        "format": "juya-public-resource-v1",
        "purpose": domain + ":" + purpose,
        "id": identifier,
        "version_id": version,
        "media_id": None,
        "note_version_id": None,
        "word_id": None,
        "cache_key": None,
        "expires": (system["time"][0] + timedelta(minutes=5)).replace(tzinfo=UTC).timestamp(),
        **references,
    }
    return P + "/public/resources/pub1_" + encrypt(system["settings"], json.dumps(data))


def resource_counts(system):
    """Observe all identity, synthesis and receipt effects in the real database."""
    with system["sessions"]() as db:
        return {
            table.name: db.scalar(select(func.count()).select_from(table))
            for table in Base.metadata.sorted_tables
            if table.name
            in {
                "users",
                "mini_sessions",
                "jobs",
                "pronunciations",
                "media_tickets",
                "operations",
                "completions",
                "daily_learning",
                "checkins",
            }
        }


def test_guest_free_text_note_metadata_and_picture_stay_open_but_resources_require_login(
    admin, system
):
    note = upload(admin)
    process_jobs(admin)
    card = publish(admin, save_note(admin, draft(admin), {"action": "set", "media_id": note["id"]}))
    listening = article(admin)
    image = admin.post(
        "/api/admin/v1/listening/articles/" + listening["id"] + "/media?kind=image",
        headers=key(),
        files={"file": ("original.png", picture(), "image/png")},
    )
    assert image.status_code == 200, image.text
    changed = admin.put(
        "/api/admin/v1/listening/articles/" + listening["id"],
        headers=key(),
        json={
            "revision": listening["revision"],
            "category_id": listening["category_id"],
            "payload": {**listening["payload"], "image_id": image.json()["id"]},
        },
    )
    assert changed.status_code == 200, changed.text
    live = publish_article(admin, changed.json())
    policy(admin, 1)
    guest = system["mini"]
    before = resource_counts(system)
    listening_image = guest.post(
        M + f"/articles/{live['id']}/media-ticket",
        headers=key(),
        json={"version_id": live["version_id"], "media_id": live["payload"]["image_id"]},
    )
    assert listening_image.status_code == 200, listening_image.text
    assert guest.get(listening_image.json()["url"]).status_code == 200
    assert (
        guest.get(
            M + f"/articles/{live['id']}/media/{live['payload']['image_id']}",
            params={"version_id": live["version_id"]},
        ).status_code
        == 200
    )
    detail = guest.get(P + f"/cards/{card['id']}").json()
    assert detail["access"]["can_learn"] is True
    assert detail["study_note"]["state"] == "ready"
    assert "url" not in detail["study_note"]
    image = guest.get(
        P + f"/cards/{card['id']}/media/{card['content']['image_id']}/url",
        params={"version_id": card["current_version_id"]},
    )
    assert image.status_code == 200, image.text
    assert guest.get(image.json()["url"]).status_code == 200
    calls = [
        (
            "GET",
            P + f"/cards/{card['id']}/media/{card['content']['audio_id']}/url",
            {"params": {"version_id": card["current_version_id"]}},
        ),
        (
            "GET",
            P + f"/cards/{card['id']}/media/{note['id']}/url",
            {
                "params": {
                    "purpose": "study_note",
                    "study_note_version_id": detail["study_note"]["version_id"],
                }
            },
        ),
        (
            "POST",
            M + f"/articles/{live['id']}/media-ticket",
            {
                "json": {"version_id": live["version_id"], "media_id": live["payload"]["audio_id"]},
                "headers": key(),
            },
        ),
    ]
    for method, path, kwargs in calls:
        response = guest.request(method, path, **kwargs)
        assert response.status_code == 401, response.text
        assert response.json()["error"]["code"] == "unauthenticated"
    for method in ("GET", "HEAD"):
        response = guest.request(
            method,
            M + f"/articles/{live['id']}/media/{live['payload']['audio_id']}",
            params={"version_id": live["version_id"]},
            headers={"Range": "bytes=0-3"},
        )
        assert response.status_code == 401
    assert resource_counts(system) == before


@pytest.mark.parametrize("domain", ["scene", "listening"])
@pytest.mark.parametrize("method", ["GET", "POST"])
def test_guest_preset_pronunciation_rejects_before_cache_or_job_effects(
    admin, system, domain, method
):
    if domain == "scene":
        row = publish(admin, draft(admin))
        path = P + f"/cards/{row['id']}/words/word-1/pronunciation"
        ref = {"version_id": row["current_version_id"]}
    else:
        row = publish_article(admin, article(admin))
        path = M + f"/articles/{row['id']}/words/any/pronunciation"
        ref = {"version_id": row["version_id"]}
    before = resource_counts(system)
    response = system["mini"].request(
        method, path, headers=key(), **({"params": ref} if method == "GET" else {"json": ref})
    )
    assert response.status_code == 401, response.text
    assert response.json()["error"]["code"] == "unauthenticated"
    assert resource_counts(system) == before


@pytest.mark.parametrize(
    "method,headers", [("GET", {}), ("HEAD", {}), ("GET", {"Range": "bytes=0-3"})]
)
def test_old_public_protected_grants_expire_even_with_a_valid_logged_in_session(
    admin, mini, system, method, headers
):
    note = upload(admin)
    process_jobs(admin)
    card = publish(admin, save_note(admin, draft(admin), {"action": "set", "media_id": note["id"]}))
    live = publish_article(admin, article(admin))
    urls = [
        legacy_public(
            system,
            "scene",
            card["id"],
            card["current_version_id"],
            "content",
            media_id=card["content"]["audio_id"],
        ),
        legacy_public(
            system,
            "scene",
            card["id"],
            card["current_version_id"],
            "study_note",
            media_id=note["id"],
            note_version_id=mini.get(P + f"/cards/{card['id']}").json()["study_note"]["version_id"],
        ),
        legacy_public(
            system,
            "scene",
            card["id"],
            card["current_version_id"],
            "word",
            word_id="word-1",
            cache_key="old-key",
        ),
        legacy_public(
            system,
            "listening",
            live["id"],
            live["version_id"],
            "content",
            media_id=live["payload"]["audio_id"],
        ),
        legacy_public(
            system,
            "listening",
            live["id"],
            live["version_id"],
            "word",
            word_id="old-word",
            cache_key="old-key",
        ),
    ]
    authorization = mini.headers.pop("Authorization")
    for identity in ({}, {"Authorization": authorization}):
        for url in urls:
            result = mini.request(method, url, headers={**headers, **identity})
            assert result.status_code == 401, result.text
            if method != "HEAD":
                assert result.json()["error"]["code"] == "public_resource_expired"
    picture = legacy_public(
        system,
        "scene",
        card["id"],
        card["current_version_id"],
        "content",
        media_id=card["content"]["image_id"],
    )
    assert mini.request(method, picture, headers=headers).status_code in {200, 206}


def test_public_delivery_uses_real_medium_kind_and_permission_cache_changes(admin, system):
    from juya_api.content_models import Media

    card = publish(admin, draft(admin))
    path = P + f"/cards/{card['id']}"
    summary = system["mini"].get(path + "/summary").json()
    assert "resource-login1" in summary["access"]["version"]
    url = legacy_public(
        system,
        "scene",
        card["id"],
        card["current_version_id"],
        "summary",
        media_id=summary["thumbnail_id"],
    )
    with system["sessions"].begin() as db:
        db.get(Media, summary["thumbnail_id"]).kind = "audio"
    assert system["mini"].get(url).status_code == 401
    set_free(admin, card["id"], False)
    assert system["mini"].get(path).json()["error"]["code"] == "content_not_open"


@pytest.mark.parametrize(
    "authorization", ["Bearer mini_invalid", "Bearer adm_invalid", "Basic invalid", "admin_session"]
)
def test_protected_routes_never_downgrade_invalid_identity_to_guest(admin, system, authorization):
    card = publish(admin, draft(admin))
    live = publish_article(admin, article(admin))
    policy(admin, 1)
    guest = system["mini"]
    if authorization == "admin_session":
        authorization = "Bearer " + admin.cookies["juya_admin_session"]
    headers = {**key(), "Authorization": authorization}
    requests = [
        (
            "GET",
            P + f"/cards/{card['id']}/media/{card['content']['audio_id']}/url",
            {"params": {"version_id": card["current_version_id"]}},
        ),
        (
            "POST",
            M + f"/articles/{live['id']}/media-ticket",
            {"json": {"version_id": live["version_id"], "media_id": live["payload"]["audio_id"]}},
        ),
        (
            "GET",
            P + f"/cards/{card['id']}/words/word-1/pronunciation",
            {"params": {"version_id": card["current_version_id"]}},
        ),
        (
            "POST",
            M + f"/articles/{live['id']}/words/any/pronunciation",
            {"json": {"version_id": live["version_id"]}},
        ),
    ]
    before = resource_counts(system)
    for method, path, kwargs in requests:
        result = guest.request(method, path, headers=headers, **kwargs)
        assert result.status_code == 401, result.text
        assert result.json()["error"]["code"] == "login_required"
    assert resource_counts(system) == before


@pytest.mark.parametrize(
    "method,headers", [("GET", {}), ("HEAD", {}), ("GET", {"Range": "bytes=0-3"})]
)
def test_private_audio_and_speech_use_live_bound_session_and_reject_other_supplied_identity(
    admin, mini, system, method, headers
):
    from juya_api.models import MiniSession
    from juya_api.security import digest
    from juya_api.worker import run_job
    from tests.content_helpers import recording

    card = publish(admin, draft(admin))
    live = publish_article(admin, article(admin))
    policy(admin, 1)
    scene_url = mini.get(
        P + f"/cards/{card['id']}/media/{card['content']['audio_id']}/url",
        params={"version_id": card["current_version_id"]},
    ).json()["url"]
    listening_url = mini.post(
        M + f"/articles/{live['id']}/media-ticket",
        json={"version_id": live["version_id"], "media_id": live["payload"]["audio_id"]},
        headers=key(),
    ).json()["url"]
    speech_path = P + f"/cards/{card['id']}/words/word-1/pronunciation"
    ref = {"version_id": card["current_version_id"]}
    job_id = mini.post(speech_path, json=ref, headers=key()).json()["job_id"]

    class Provider:
        def synthesize(self, text, config, session):
            return recording()

    run_job(
        system["settings"], system["sessions"], job_id, clock=admin.app.state.clock, tts=Provider()
    )
    speech_url = mini.get(speech_path, params=ref).json()["url"]
    other = mini.post(
        P + "/auth/wechat",
        headers=key(),
        json={"code": "bob:resource", "consent": True, "consent_version": "2026-10-17"},
    )
    assert other.status_code == 200, other.text
    other_token = "Bearer " + other.json()["access_token"]
    token = mini.headers.pop("Authorization")
    for url in (scene_url, listening_url, speech_url):
        assert mini.request(method, url, headers=headers).status_code in {200, 206}
        for authorization in ("Bearer adm_invalid", other_token, token.removeprefix("Bearer ")):
            assert (
                mini.request(
                    method, url, headers={**headers, "Authorization": authorization}
                ).status_code
                == 401
            )
    with system["sessions"].begin() as db:
        db.get(MiniSession, digest(token.removeprefix("Bearer "))).expires_at = system["time"][0]
    for url in (scene_url, listening_url, speech_url):
        assert mini.request(method, url, headers=headers).status_code == 401


@pytest.mark.parametrize("endpoint", ["thumbnail", "thumbnail-ticket"])
def test_guest_listening_thumbnail_cannot_claim_an_audio_kind(admin, system, endpoint):
    """A summary purpose cannot authorize an actual audio even before public issuance."""
    from juya_api.content_models import Media

    row = article(admin)
    uploaded = admin.post(
        "/api/admin/v1/listening/articles/" + row["id"] + "/media?kind=image",
        headers=key(),
        files={"file": ("original.png", picture(), "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    changed = admin.put(
        "/api/admin/v1/listening/articles/" + row["id"],
        headers=key(),
        json={
            "revision": row["revision"],
            "category_id": row["category_id"],
            "payload": {**row["payload"], "image_id": uploaded.json()["id"]},
        },
    )
    assert changed.status_code == 200, changed.text
    live = publish_article(admin, changed.json())
    with system["sessions"].begin() as db:
        db.get(Media, uploaded.json()["thumbnail_id"]).kind = "audio"
    response = system["mini"].get(
        M + f"/articles/{live['id']}/{endpoint}",
        params={"version_id": live["version_id"]},
    )
    assert response.status_code == 401, response.text
    assert response.json()["error"]["code"] == "unauthenticated"
