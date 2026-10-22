"""Revision15 list filtering and stable source queues with real SQL persistence."""

from .content_helpers import content, draft, key, publish


def cards(admin, count=3):
    """Publish distinct cards sharing valid media to keep the scenario focused."""
    payload = content(admin)
    return [publish(admin, draft(admin, {**payload, "name": f"场景{i}"})) for i in range(count)]


def test_incomplete_filter_precedes_pagination_and_keeps_published_count(admin, mini):
    values = cards(admin)
    first = mini.get("/api/mini/v1/cards?limit=1").json()["items"][0]
    response = mini.post(
        f"/api/mini/v1/cards/{first['id']}/complete",
        headers=key(),
        json={"version_id": first["version_id"]},
    )
    assert response.status_code == 200
    listing = mini.get("/api/mini/v1/cards?limit=1").json()
    assert listing["total"] == 2
    assert listing["published_total"] == 3
    assert len(listing["items"]) == 1
    assert listing["items"][0]["id"] != first["id"]
    original = next(card for card in values if card["id"] == first["id"])
    publish(admin, original)
    assert mini.get("/api/mini/v1/cards").json()["total"] == 2


def test_no_published_and_all_learned_are_different(admin, mini):
    assert mini.get("/api/mini/v1/cards").json()["published_total"] == 0
    card = cards(admin, 1)[0]
    mini.post(
        f"/api/mini/v1/cards/{card['id']}/complete",
        headers=key(),
        json={"version_id": card["current_version_id"]},
    )
    result = mini.get("/api/mini/v1/cards").json()
    assert (result["total"], result["published_total"]) == (0, 1)


def test_authorized_detail_starts_reading_without_awarding_completion(admin, mini):
    card = cards(admin, 1)[0]
    mini.get(f"/api/mini/v1/cards/{card['id']}").raise_for_status()
    state = mini.get("/api/mini/v1/cards").json()["items"][0]["state"]
    assert state["started"] is True
    assert state["completed"] is False
    assert mini.get("/api/mini/v1/me/statistics").json()["completed_cards"] == 0


def test_thumbnail_metadata_fallback_does_not_mark_an_unopened_card_started(admin, mini):
    card = cards(admin, 1)[0]
    response = mini.get(f"/api/mini/v1/cards/{card['id']}?mark_started=false")
    assert response.status_code == 200
    assert response.json()["state"]["started"] is False
    assert mini.get("/api/mini/v1/cards").json()["items"][0]["state"]["started"] is False
    mini.get(f"/api/mini/v1/cards/{card['id']}").raise_for_status()
    assert mini.get("/api/mini/v1/cards").json()["items"][0]["state"]["started"] is True


def test_reading_position_is_owned_and_bound_to_exact_published_version(admin, mini):
    card = cards(admin, 1)[0]
    body = {"version_id": card["current_version_id"], "anchor": "dialogue:line-1", "progress": 0.4}
    response = mini.put(
        f"/api/mini/v1/cards/{card['id']}/reading-position", headers=key(), json=body
    )
    assert response.status_code == 200, response.text
    assert response.json() == body
    detail = mini.get(f"/api/mini/v1/cards/{card['id']}").json()
    assert detail["reading_position"] == body
    assert detail["state"]["completed"] is False
    token = mini.post(
        "/api/mini/v1/auth/wechat",
        headers=key(),
        json={"code": "bob:position", "consent": True, "consent_version": "2026-10-17"},
    ).json()["access_token"]
    assert (
        mini.get(
            f"/api/mini/v1/cards/{card['id']}", headers={"Authorization": f"Bearer {token}"}
        ).json()["reading_position"]
        is None
    )
    # 同一用户重新主动登录，恢复相同可信位置
    token = mini.post(
        "/api/mini/v1/auth/wechat",
        headers=key(),
        json={"code": "alice:position", "consent": True, "consent_version": "2026-10-17"},
    ).json()["access_token"]
    mini.headers["Authorization"] = f"Bearer {token}"
    assert mini.get(f"/api/mini/v1/cards/{card['id']}").json()["reading_position"] == body
    saved = admin.put(
        f"/api/admin/v1/cards/{card['id']}",
        headers=key(),
        json={
            "revision": card["draft_revision"],
            "content": {**card["content"], "name": "更新后的场景"},
        },
    )
    assert saved.status_code == 200
    updated = publish(admin, saved.json())
    assert updated["current_version_id"] != body["version_id"]
    latest = mini.get(f"/api/mini/v1/cards/{card['id']}").json()
    assert latest["reading_position"] is None
    assert latest["reading_position_reset"] is True
    assert (
        mini.put(
            f"/api/mini/v1/cards/{card['id']}/reading-position", headers=key(), json=body
        ).status_code
        == 409
    )


def test_reading_position_rejects_foreign_anchor_and_keeps_scores_unchanged(admin, mini):
    card = cards(admin, 1)[0]
    body = {"version_id": card["current_version_id"], "anchor": "dialogue:absent", "progress": 0.4}
    assert (
        mini.put(
            f"/api/mini/v1/cards/{card['id']}/reading-position", headers=key(), json=body
        ).status_code
        == 422
    )
    assert (
        mini.put(
            f"/api/mini/v1/cards/{card['id']}/reading-position",
            headers=key(),
            json={**body, "anchor": "top", "progress": 1.1},
        ).status_code
        == 422
    )
    headers = key()
    body = {**body, "anchor": "vocabulary:word-1", "progress": 0.2}
    first = mini.put(
        f"/api/mini/v1/cards/{card['id']}/reading-position", headers=headers, json=body
    )
    second = mini.put(
        f"/api/mini/v1/cards/{card['id']}/reading-position", headers=headers, json=body
    )
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json() == body
    stats = mini.get("/api/mini/v1/me/statistics").json()
    assert stats["completed_cards"] == stats["total_checkin_days"] == 0


def test_queue_freezes_order_from_clicked_card_and_revalidates_later_rows(admin, mini):
    cards(admin, 4)
    listing = mini.get("/api/mini/v1/cards").json()["items"]
    response = mini.post(
        "/api/mini/v1/learning-queues",
        headers=key(),
        json={"source": "learning", "card_id": listing[1]["id"]},
    )
    assert response.status_code == 201, response.text
    queue = response.json()
    assert queue["total"] == 3
    # Removing the current card from the source list must not shift the next page
    mini.post(
        f"/api/mini/v1/cards/{listing[1]['id']}/complete",
        headers=key(),
        json={"version_id": listing[1]["version_id"]},
    )
    cards(admin, 1)
    page = mini.get(f"/api/mini/v1/learning-queues/{queue['id']}?offset=1&limit=1").json()
    assert page["items"][0]["card_id"] == listing[2]["id"]
    assert page["next_offset"] == 2
    mini.post(
        f"/api/mini/v1/cards/{listing[2]['id']}/complete",
        headers=key(),
        json={"version_id": listing[2]["version_id"]},
    )
    refreshed = mini.get(f"/api/mini/v1/learning-queues/{queue['id']}?offset=1").json()
    assert refreshed["items"][0]["available"] is False
    assert refreshed["items"][1]["card_id"] == listing[3]["id"]
    assert refreshed["next_offset"] is None


def test_queue_is_owned_and_favorite_relationship_is_rechecked(admin, mini):
    card = cards(admin, 1)[0]
    mini.put(
        f"/api/mini/v1/cards/{card['id']}/favorite",
        headers=key(),
        json={"version_id": card["current_version_id"]},
    )
    created = mini.post(
        "/api/mini/v1/learning-queues",
        headers=key(),
        json={"source": "favorites", "card_id": card["id"]},
    ).json()
    mini.delete(f"/api/mini/v1/favorites/{card['id']}", headers=key())
    assert (
        mini.get(f"/api/mini/v1/learning-queues/{created['id']}").json()["items"][0]["available"]
        is False
    )
    token = mini.post(
        "/api/mini/v1/auth/wechat",
        headers=key(),
        json={"code": "bob:new", "consent": True, "consent_version": "2026-10-17"},
    ).json()["access_token"]
    assert (
        mini.get(
            f"/api/mini/v1/learning-queues/{created['id']}",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 404
    )


def test_queue_creation_replay_survives_completion_and_rejects_changed_source(admin, mini):
    card = cards(admin, 1)[0]
    headers = key()
    body = {"source": "learning", "card_id": card["id"]}
    first = mini.post("/api/mini/v1/learning-queues", headers=headers, json=body)
    mini.post(
        f"/api/mini/v1/cards/{card['id']}/complete",
        headers=key(),
        json={"version_id": card["current_version_id"]},
    )
    second = mini.post("/api/mini/v1/learning-queues", headers=headers, json=body)
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert (
        mini.post(
            "/api/mini/v1/learning-queues", headers=headers, json={**body, "source": "records"}
        ).status_code
        == 409
    )


def test_records_snapshot_does_not_reorder_after_review_and_day_stays_scoped(admin, mini, system):
    from datetime import timedelta

    values = cards(admin, 3)
    for card in values:
        mini.post(
            f"/api/mini/v1/cards/{card['id']}/complete",
            headers=key(),
            json={"version_id": card["current_version_id"]},
        )
        system["time"][0] += timedelta(minutes=1)
    original = mini.get("/api/mini/v1/me/learning-records").json()["items"]
    queue = mini.post(
        "/api/mini/v1/learning-queues",
        headers=key(),
        json={"source": "records", "card_id": original[0]["id"]},
    ).json()
    last = next(card for card in values if card["id"] == original[-1]["id"])
    system["time"][0] += timedelta(days=1)
    mini.post(
        f"/api/mini/v1/cards/{last['id']}/complete",
        headers=key(),
        json={"version_id": last["current_version_id"]},
    )
    # 24-hour snapshot expiry is independent of history order
    system["time"][0] -= timedelta(days=1)
    page = mini.get(f"/api/mini/v1/learning-queues/{queue['id']}").json()
    assert [row["card_id"] for row in page["items"]] == [row["id"] for row in original]
    day = mini.post(
        "/api/mini/v1/learning-queues",
        headers=key(),
        json={"source": "day", "card_id": last["id"], "day": "2026-10-18"},
    ).json()
    assert day["total"] == 1


def test_expired_queue_and_invalid_day_reference_are_explicit(admin, mini, system):
    from datetime import timedelta

    card = cards(admin, 1)[0]
    queue = mini.post(
        "/api/mini/v1/learning-queues",
        headers=key(),
        json={"source": "learning", "card_id": card["id"]},
    ).json()
    system["time"][0] += timedelta(hours=24)
    response = mini.get(f"/api/mini/v1/learning-queues/{queue['id']}")
    assert response.status_code == 410
    assert response.json()["error"]["code"] == "queue_expired"
    for body in [
        {"source": "day", "card_id": card["id"]},
        {"source": "learning", "card_id": card["id"], "day": "2026-10-17"},
    ]:
        assert (
            mini.post("/api/mini/v1/learning-queues", headers=key(), json=body).status_code == 422
        )


def test_offline_detail_cannot_create_reading_start_or_queue(admin, mini, system):
    from sqlalchemy import select

    from juya_api.discovery_models import ReadingStart

    card = cards(admin, 1)[0]
    admin.post(
        f"/api/admin/v1/cards/{card['id']}/offline",
        headers=key(),
        json={"revision": card["draft_revision"]},
    )
    assert mini.get(f"/api/mini/v1/cards/{card['id']}").status_code == 410
    with system["sessions"]() as db:
        assert list(db.scalars(select(ReadingStart))) == []
    assert (
        mini.post(
            "/api/mini/v1/learning-queues",
            headers=key(),
            json={"source": "learning", "card_id": card["id"]},
        ).status_code
        == 410
    )
