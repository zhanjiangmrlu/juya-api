"""Deleted content disappears from learner collections without rewriting learning facts."""

from tests.content_helpers import key
from tests.test_integration05_catalog import catalog_topic
from tests.test_learning import complete, scene
from tests.test_listening import A, M, article, policy, post, publish


def test_listening_delete_hides_collections_and_preserves_historical_day_counts(admin, mini):
    _, topic = catalog_topic(admin)
    first, second = [
        publish(admin, article(admin, topic["id"], title)) for title in ["保留", "删除"]
    ]
    policy(admin, 2)
    for row in [first, second]:
        assert (
            mini.put(
                M + f"/articles/{row['id']}/favorite",
                headers=key(),
                json={"version_id": row["version_id"]},
            ).status_code
            == 200
        )
        post(mini, M + f"/articles/{row['id']}/complete", {"version_id": row["version_id"]})
    before = mini.get(M + "/statistics").json()
    day = before["date"]
    post(admin, A + f"/articles/{second['id']}/delete", {"revision": second["revision"]})
    for path in ["/favorites?limit=1", "/records?limit=1"]:
        result = mini.get(M + path).json()
        assert result["total"] == 1
        assert [r["id"] for r in result["items"]] == [first["id"]]
    after = mini.get(M + "/statistics").json()
    assert after["listening_favorite_count"] == 1
    for field in [
        "completed_articles",
        "today_completed_articles",
        "total_checkin_days",
        "current_streak",
    ]:
        assert after[field] == before[field]
    details = mini.get(M + f"/checkins/{day}").json()
    assert [row["id"] for row in details["article_items"]] == [first["id"]]
    assert details["article_count"] == 2
    assert mini.get(M + "/checkins").json()["items"][0]["article_count"] == 2


def test_scene_delete_hides_favorites_but_retains_checkin_count_and_offline_placeholder(
    admin, mini
):
    card, version = scene(admin)
    assert (
        mini.put(
            f"/api/mini/v1/cards/{card['id']}/favorite", headers=key(), json={"version_id": version}
        ).status_code
        == 200
    )
    result = complete(mini, card, version).json()
    assert (
        admin.post(
            f"/api/admin/v1/cards/{card['id']}/offline", headers=key(), json={"revision": 1}
        ).status_code
        == 200
    )
    assert mini.get("/api/mini/v1/favorites").json()["total"] == 1
    current = admin.get(f"/api/admin/v1/cards/{card['id']}").json()
    response = admin.request(
        "DELETE",
        f"/api/admin/v1/cards/{card['id']}",
        headers=key(),
        json={"revision": current["draft_revision"]},
    )
    assert response.status_code == 200, response.text
    assert mini.get("/api/mini/v1/favorites").json()["items"] == []
    stats = mini.get("/api/mini/v1/me/statistics").json()
    assert stats["favorite_count"] == 0 and stats["completed_cards"] == 1
    checkin = mini.get("/api/mini/v1/me/checkins").json()["items"][0]
    assert checkin["date"] == result["date"] and checkin["card_count"] == 1
