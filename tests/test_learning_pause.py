"""Paused learning authorization must fence resources for every account state."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from juya_api.models import AdminSession, MiniSession
from tests.content_helpers import key
from tests.test_guest_content import set_free
from tests.test_integration06 import article, category, publish
from tests.test_learning_access import change, user_id
from tests.test_revision15_learning import cards


@pytest.mark.parametrize("identity", ["guest", "none", "active", "expired", "revoked"])
def test_only_explicit_free_content_is_open_for_every_identity(admin, mini, system, identity):
    """An active grant must not bypass the paused policy in either catalog."""
    scene = cards(admin, 1)[0]
    owner = category(admin)
    listening = publish(admin, article(admin, owner["id"]))
    uid = user_id(mini)
    if identity in {"active", "expired", "revoked"}:
        change(admin, uid, "grant")
    if identity == "revoked":
        change(admin, uid, "revoke")
    if identity == "expired":
        with system["sessions"].begin() as db:
            for model in (AdminSession, MiniSession):
                db.execute(update(model).values(expires_at=datetime(2030, 1, 1, tzinfo=UTC)))
        system["time"][0] += timedelta(days=40)
    if identity == "guest":
        mini.headers.pop("Authorization")
    for row, is_listening in ((scene, False), (listening, True)):
        path = "/api/mini/v1/" + ("listening/articles/" if is_listening else "cards/") + row["id"]
        set_free(admin, row["id"], True, listening=is_listening)
        opened = mini.get(path)
        assert opened.status_code == 200, opened.text
        assert opened.json()["access"]["can_learn"] is True
        assert opened.json()["access"]["can_lookup"] is False
        assert opened.json()["access"]["expires_at"] is None
        set_free(admin, row["id"], False, listening=is_listening)
        summary = mini.get(path + "/summary").json()
        assert summary["access"]["can_learn"] is False
        assert summary["access"]["reason"] == "content_not_open"
        denied = mini.get(path)
        assert denied.status_code == 403, denied.text
        assert denied.json()["error"]["code"] == "content_not_open"
        assert "暂未开放" in denied.json()["error"]["message"]
    categories = mini.get("/api/mini/v1/listening/home").json()
    assert categories["categories"][0]["restricted_articles"] == 1
    if identity == "active":
        assert (
            admin.get(f"/api/admin/v1/users/{uid}/learning-authorization").json()["status"]
            == "active"
        )


def test_paused_dictionary_is_unavailable_even_with_active_grant(admin, mini):
    """Free preset audio stays usable while arbitrary lookup is dormant."""
    from tests.test_dictionary import scenario

    scene = scenario(admin)
    change(admin, user_id(mini), "grant")
    path = f"/api/mini/v1/cards/{scene['id']}"
    response = mini.get(
        path + "/dictionary",
        params={
            "version_id": scene["current_version_id"],
            "word": "went",
            "line_id": "line-1",
            "start": 3,
            "end": 7,
        },
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "lookup_unavailable"
    speech = mini.post(
        path + "/words/word-0/pronunciation",
        headers=key(),
        json={"version_id": scene["current_version_id"]},
    )
    assert speech.status_code == 200, speech.text


def test_paused_mode_invalidates_old_media_tickets_and_keeps_grant_history(
    admin, mini, monkeypatch
):
    """Old packages and signed resource URLs cannot bypass the live free-only decision."""
    from juya_api import learning_features
    from tests.test_listening import post

    scene = cards(admin, 1)[0]
    owner = category(admin)
    listening = publish(admin, article(admin, owner["id"]))
    change(admin, user_id(mini), "grant")
    for row, listening_mode in ((scene, False), (listening, True)):
        set_free(admin, row["id"], False, listening=listening_mode)
    monkeypatch.setattr(learning_features, "LEARNING_AUTHORIZATION_ENABLED", True)
    monkeypatch.setattr(learning_features, "IN_APP_DICTIONARY_ENABLED", True)
    scene_path = f"/api/mini/v1/cards/{scene['id']}"
    listening_path = f"/api/mini/v1/listening/articles/{listening['id']}"
    version_before = mini.get(scene_path).json()["access"]["version"]
    scene_ticket = mini.get(
        scene_path + f"/media/{scene['content']['audio_id']}/url",
        params={"version_id": scene["current_version_id"]},
    ).json()["url"]
    article_ticket = post(
        mini,
        listening_path + "/media-ticket",
        {
            "version_id": listening["version_id"],
            "media_id": listening["payload"]["audio_id"],
        },
    )["url"]
    monkeypatch.setattr(learning_features, "LEARNING_AUTHORIZATION_ENABLED", False)
    monkeypatch.setattr(learning_features, "IN_APP_DICTIONARY_ENABLED", False)
    for url in (scene_ticket, article_ticket):
        for method in ("get", "head"):
            assert getattr(mini, method)(url, headers={"Range": "bytes=0-15"}).status_code == 403
    after = mini.get(scene_path + "/summary").json()["access"]
    assert after["version"] != version_before
    assert after["reason"] == "content_not_open"
    for path, version in (
        (scene_path, scene["current_version_id"]),
        (listening_path, listening["version_id"]),
    ):
        response = mini.post(path + "/complete", headers=key(), json={"version_id": version})
        assert response.status_code == 403, response.text
    assert mini.get("/api/mini/v1/listening/home").json()["continue_learning"] is None
    monkeypatch.setattr(learning_features, "LEARNING_AUTHORIZATION_ENABLED", True)
    monkeypatch.setattr(learning_features, "IN_APP_DICTIONARY_ENABLED", True)
    assert mini.get(scene_path).status_code == 200
    assert mini.get(listening_path).status_code == 200


def test_active_grant_cannot_select_closed_next_or_continue_targets(admin, mini, monkeypatch):
    """Frozen queues and saved history must use the paused permission decision."""
    from juya_api import learning_features

    owner = category(admin)
    first, following, closed = [publish(admin, article(admin, owner["id"])) for _ in range(3)]
    for row in (first, following):
        set_free(admin, row["id"], True, listening=True)
    set_free(admin, closed["id"], False, listening=True)
    change(admin, user_id(mini), "grant")
    monkeypatch.setattr(learning_features, "LEARNING_AUTHORIZATION_ENABLED", True)
    path = f"/api/mini/v1/listening/articles/{closed['id']}"
    saved = mini.put(
        path + "/progress",
        headers=key(),
        json={
            "version_id": closed["version_id"],
            "reading_position": 1,
            "translation_open": False,
            "audio_position": 0.1,
            "playback_rate": 1,
        },
    )
    assert saved.status_code == 200, saved.text
    frozen = mini.get(f"/api/mini/v1/listening/articles/{following['id']}").json()["queue_token"]
    monkeypatch.setattr(learning_features, "LEARNING_AUTHORIZATION_ENABLED", False)
    assert mini.get("/api/mini/v1/listening/home").json()["continue_learning"] is None
    path = f"/api/mini/v1/listening/articles/{first['id']}/next"
    assert mini.get(path).json()["article"]["id"] == following["id"]
    path = f"/api/mini/v1/listening/articles/{following['id']}/next"
    result = mini.get(path, params={"queue_token": frozen}).json()
    assert result["ended"] is True and result["article"] is None


def test_listening_lookup_is_closed_but_free_preset_pronunciation_stays_available(admin, mini):
    """A retained valid grant must not reactivate arbitrary listening dictionary calls."""
    from tests.test_integration06 import vocabulary

    owner = category(admin)
    row = publish(admin, article(admin, owner["id"], vocabulary()))
    set_free(admin, row["id"], True, listening=True)
    change(admin, user_id(mini), "grant")
    path = f"/api/mini/v1/listening/articles/{row['id']}"
    result = mini.get(
        path + "/dictionary",
        params={
            "version_id": row["version_id"],
            "start": 3,
            "end": 7,
        },
    )
    assert result.status_code == 403, result.text
    assert result.json()["error"]["code"] == "lookup_unavailable"
    params = {"version_id": row["version_id"]}
    assert mini.get(path + "/words/rest-one/pronunciation", params=params).status_code == 200
    set_free(admin, row["id"], False, listening=True)
    assert mini.get(path + "/words/rest-one/pronunciation", params=params).status_code == 403
