"""Real HTTP/SQL checks for authorization, free ordering and revocable resources."""

from datetime import UTC, datetime

import pytest

from .content_helpers import key
from .test_revision15_learning import cards


@pytest.fixture(autouse=True)
def valid_sessions(system, admin, mini):
    from sqlalchemy import update

    from juya_api.models import AdminSession, MiniSession

    with system["sessions"].begin() as db:
        for model in (AdminSession, MiniSession):
            db.execute(update(model).values(expires_at=datetime(2030, 1, 1)))


POLICY = "/api/admin/v1/learning-access/free-policy"


def configure(admin, n):
    admin.app.state.settings.learning_access_activation_ready = True
    preview = admin.post(POLICY + "/preview", json={"free_count": n})
    assert preview.status_code == 200, preview.text
    response = admin.put(
        POLICY, headers=key(), json={"preview_token": preview.json()["preview_token"]}
    )
    assert response.status_code == 200, response.text
    return response.json()


def user_id(mini):
    return mini.get("/api/mini/v1/me").json()["id"]


def change(admin, uid, action, expires_on=None):
    path = f"/api/admin/v1/users/{uid}/learning-authorization"
    preview = admin.post(path + "/preview", json={"action": action, "expires_on": expires_on})
    assert preview.status_code == 200, preview.text
    response = admin.put(
        path, headers=key(), json={"preview_token": preview.json()["preview_token"]}
    )
    assert response.status_code == 200, response.text
    return response


def test_unconfigured_does_not_gift_authorization(mini):
    response = mini.get("/api/mini/v1/learning-access")
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert response.json()["free_count"] is None
    assert response.json()["authorization"]["status"] == "none"


@pytest.mark.parametrize("n", [-1, 1.5, "", "2", None, True])
def test_invalid_count_does_not_enable(admin, mini, n):
    assert admin.post(POLICY + "/preview", json={"free_count": n}).status_code == 422
    assert mini.get("/api/mini/v1/learning-access").json()["enabled"] is False


def test_free_set_precedes_completed_filter_and_keeps_locked_summary(admin, mini):
    cards(admin, 3)
    first, second, third = mini.get("/api/mini/v1/cards").json()["items"]
    configure(admin, 2)
    response = mini.post(
        f"/api/mini/v1/cards/{first['id']}/complete",
        headers=key(),
        json={"version_id": first["version_id"]},
    )
    assert response.status_code == 200
    listing = mini.get("/api/mini/v1/cards?limit=1&page=2").json()
    assert listing["total"] == 2
    assert listing["items"][0]["id"] == third["id"]
    assert listing["items"][0]["access"]["can_learn"] is False
    assert mini.get(f"/api/mini/v1/cards/{second['id']}").status_code == 200
    assert mini.get(f"/api/mini/v1/cards/{third['id']}").status_code == 403
    safe = mini.get(f"/api/mini/v1/cards/{third['id']}/access").json()
    assert safe["summary"]["id"] == third["id"]
    assert "content" not in safe


def test_outdated_free_preview_is_rejected(admin, mini):
    cards(admin, 1)
    preview = admin.post(POLICY + "/preview", json={"free_count": 1}).json()
    cards(admin, 1)
    response = admin.put(POLICY, headers=key(), json={"preview_token": preview["preview_token"]})
    assert response.status_code == 409
    assert mini.get("/api/mini/v1/learning-access").json()["enabled"] is False


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        ("2027-01-31", "2027-02-28"),
        ("2028-01-31", "2028-02-29"),
        ("2026-10-25", "2026-11-25"),
        ("2026-12-31", "2027-01-31"),
        ("2028-02-29", "2028-03-29"),
    ],
)
def test_natural_month_and_expiry_boundary(admin, mini, system, day, expected):
    from sqlalchemy import update

    from juya_api.models import AdminSession, MiniSession

    with system["sessions"].begin() as db:
        for model in (AdminSession, MiniSession):
            db.execute(update(model).values(expires_at=datetime(2030, 1, 1)))
    system["time"][0] = datetime.fromisoformat(day + "T04:00:00+00:00")
    result = change(admin, user_id(mini), "grant").json()
    assert result["expires_on"] == expected
    system["time"][0] = datetime.fromisoformat(expected + "T15:59:59+00:00")
    assert mini.get("/api/mini/v1/learning-access").json()["authorization"]["status"] == "active"
    system["time"][0] = datetime.fromisoformat(expected + "T16:00:00+00:00")
    assert mini.get("/api/mini/v1/learning-access").json()["authorization"]["status"] == "expired"


def test_renewal_idempotency_and_revocation_history(admin, mini, system):
    system["time"][0] = datetime(2026, 10, 25, 4, tzinfo=UTC)
    uid = user_id(mini)
    change(admin, uid, "set_expiry", "2026-11-24")
    path = f"/api/admin/v1/users/{uid}/learning-authorization"
    preview = admin.post(path + "/preview", json={"action": "renew"}).json()
    body, headers = {"preview_token": preview["preview_token"]}, key()
    first = admin.put(path, headers=headers, json=body)
    again = admin.put(path, headers=headers, json=body)
    assert first.status_code == again.status_code == 200
    assert first.json() == again.json()
    assert first.json()["expires_on"] == "2026-12-24"
    change(admin, uid, "revoke")
    assert mini.get("/api/mini/v1/learning-access").json()["authorization"]["status"] == "none"
    assert admin.get(path + "/history").json()["total"] == 3
    assert admin.put(path, headers=headers, json=body).json() == first.json()


def test_free_learning_retains_audio_but_blocks_body_dictionary(admin, mini):
    card = cards(admin, 1)[0]
    configure(admin, 1)
    ref = {
        "version_id": card["current_version_id"],
        "word": "Hello",
        "line_id": "line-1",
        "start": 0,
        "end": 5,
    }
    assert mini.get(f"/api/mini/v1/cards/{card['id']}/dictionary", params=ref).status_code == 403
    detail = mini.get(f"/api/mini/v1/cards/{card['id']}").json()
    assert detail["content"]["audio_id"]
    assert detail["access"]["can_learn"] is True
    assert detail["access"]["can_lookup"] is False


def test_revocation_blocks_old_media_and_completion_but_allows_unfavorite(admin, mini):
    card = cards(admin, 1)[0]
    uid = user_id(mini)
    change(admin, uid, "grant")
    configure(admin, 0)
    cid, version = card["id"], card["current_version_id"]
    body = {"version_id": version}
    assert (
        mini.put(f"/api/mini/v1/cards/{cid}/favorite", headers=key(), json=body).status_code == 200
    )
    audio = card["content"]["audio_id"]
    ticket = mini.get(
        f"/api/mini/v1/cards/{cid}/media/{audio}/url", params={"version_id": version}
    ).json()["url"]
    change(admin, uid, "revoke")
    for method in ("get", "head"):
        assert getattr(mini, method)(ticket, headers={"Range": "bytes=0-10"}).status_code == 403
    assert (
        mini.post(f"/api/mini/v1/cards/{cid}/complete", headers=key(), json=body).status_code == 403
    )
    assert mini.delete(f"/api/mini/v1/favorites/{cid}", headers=key()).status_code == 200
    assert mini.get("/api/mini/v1/me/statistics").json()["completed_cards"] == 0


def test_free_preset_speech_and_active_body_lookup_have_distinct_permissions(admin, mini):
    from .test_dictionary import scenario

    card = scenario(admin)
    configure(admin, 1)
    path = f"/api/mini/v1/cards/{card['id']}"
    speech = mini.post(
        path + "/words/word-0/pronunciation",
        headers=key(),
        json={"version_id": card["current_version_id"]},
    )
    assert speech.status_code == 200, speech.text
    ref = {
        "version_id": card["current_version_id"],
        "word": "went",
        "line_id": "line-1",
        "start": 3,
        "end": 7,
    }
    assert mini.get(path + "/dictionary", params=ref).status_code == 403
    change(admin, user_id(mini), "grant")
    response = mini.get(path + "/dictionary", params=ref)
    assert response.status_code == 200, response.text
    assert response.json()["source"] == "context"


def test_publication_changes_free_membership_without_changing_completion_history(admin, mini):
    cards(admin, 2)
    first = mini.get("/api/mini/v1/cards").json()["items"][0]
    configure(admin, 1)
    assert (
        mini.post(
            f"/api/mini/v1/cards/{first['id']}/complete",
            headers=key(),
            json={"version_id": first["version_id"]},
        ).status_code
        == 200
    )
    assert mini.get("/api/mini/v1/cards").json()["free_uncompleted_total"] == 0
    new_card = cards(admin, 1)[0]
    assert (
        mini.get(f"/api/mini/v1/cards/{new_card['id']}/access").json()["access"]["is_free"] is True
    )
    assert (
        mini.get(f"/api/mini/v1/cards/{first['id']}/access").json()["access"]["can_learn"] is False
    )
    assert mini.get("/api/mini/v1/me/statistics").json()["completed_cards"] == 1


def test_expired_grant_reopens_from_current_server_day(admin, mini, system):
    uid = user_id(mini)
    change(admin, uid, "set_expiry", "2026-10-17")
    system["time"][0] = datetime(2026, 10, 25, 4, tzinfo=UTC)
    assert (
        admin.get(f"/api/admin/v1/users/{uid}/learning-authorization").json()["status"] == "expired"
    )
    result = change(admin, uid, "grant").json()
    assert result["starts_on"] == "2026-10-25"
    assert result["expires_on"] == "2026-11-25"
