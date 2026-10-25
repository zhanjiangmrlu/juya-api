"""Cross-entry safety: old tickets, frozen queues and confirmed mutations."""

from .content_helpers import key
from .test_learning_access import POLICY, change, configure, user_id
from .test_revision15_learning import cards


def test_activation_requires_deployment_ready_gate(admin, mini):
    preview = admin.post(POLICY + "/preview", json={"free_count": 0}).json()
    response = admin.put(POLICY, headers=key(), json={"preview_token": preview["preview_token"]})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "access_rollout_not_ready"
    assert mini.get("/api/mini/v1/learning-access").json()["enabled"] is False


def test_zero_and_oversize_free_counts_and_global_preview_pagination(admin, mini):
    cards(admin, 3)
    configure(admin, 0)
    assert all(not r["access"]["can_learn"] for r in mini.get("/api/mini/v1/cards").json()["items"])
    preview = admin.post(POLICY + "/preview?limit=1&page=2", json={"free_count": 99}).json()
    assert preview["total"] == 3 and len(preview["items"]) == 1
    assert configure(admin, 99)["actual_free_count"] == 3
    assert all(r["access"]["is_free"] for r in mini.get("/api/mini/v1/cards").json()["items"])


def test_stale_grant_preview_and_invalid_dates_leave_current_authorization(admin, mini):
    uid = user_id(mini)
    path = f"/api/admin/v1/users/{uid}/learning-authorization"
    for value in (None, "", "2020-01-01", "not-a-date"):
        assert (
            admin.post(
                path + "/preview", json={"action": "set_expiry", "expires_on": value}
            ).status_code
            == 422
        )
    old = admin.post(path + "/preview", json={"action": "grant"}).json()
    change(admin, uid, "grant")
    assert (
        admin.put(path, headers=key(), json={"preview_token": old["preview_token"]}).status_code
        == 409
    )
    assert admin.get(path + "/history").json()["total"] == 1
    for action in ("grant",):
        assert admin.post(path + "/preview", json={"action": action}).status_code == 409


def test_queued_rows_recheck_access_without_reordering_or_inserting_new_free_cards(admin, mini):
    cards(admin, 3)
    rows = mini.get("/api/mini/v1/cards").json()["items"]
    queue = mini.post(
        "/api/mini/v1/learning-queues",
        headers=key(),
        json={"source": "learning", "card_id": rows[0]["id"]},
    ).json()
    configure(admin, 1)
    result = mini.get(f"/api/mini/v1/learning-queues/{queue['id']}?limit=2").json()
    assert [r["card_id"] for r in result["items"]] == [r["id"] for r in rows[:2]]
    assert [r["available"] for r in result["items"]] == [True, False]
    assert result["next_offset"] == 2
    assert (
        mini.post(
            "/api/mini/v1/learning-queues",
            headers=key(),
            json={"source": "learning", "card_id": rows[-1]["id"]},
        ).status_code
        == 403
    )


def test_successful_completion_replays_after_permission_loss_without_new_checkin(admin, mini):
    card = cards(admin, 1)[0]
    headers, body = key(), {"version_id": card["current_version_id"]}
    path = f"/api/mini/v1/cards/{card['id']}/complete"
    first = mini.post(path, headers=headers, json=body)
    configure(admin, 0)
    assert mini.post(path, headers=headers, json=body).json() == first.json()
    assert mini.post(path, headers=key(), json=body).status_code == 403
    assert mini.get("/api/mini/v1/me/statistics").json()["completed_cards"] == 1


def test_locked_published_thumbnail_never_authorizes_original_or_reading_position(admin, mini):
    card = cards(admin, 1)[0]
    detail = mini.get(f"/api/mini/v1/cards/{card['id']}").json()
    configure(admin, 0)
    path = f"/api/mini/v1/cards/{card['id']}"
    params = {"version_id": card["current_version_id"], "purpose": "summary"}
    thumb = mini.get(f"{path}/media/{detail['thumbnail_id']}/url", params=params)
    assert thumb.status_code == 200
    assert mini.get(thumb.json()["url"]).status_code == 200
    assert (
        mini.get(f"{path}/media/{card['content']['image_id']}/url", params=params).status_code
        == 404
    )
    assert (
        mini.put(
            path + "/reading-position",
            headers=key(),
            json={"version_id": card["current_version_id"], "anchor": "top", "progress": 0},
        ).status_code
        == 403
    )
    assert admin.get(f"/api/admin/v1/cards/{card['id']}/published").status_code == 200


def test_non_administrator_cannot_enable_or_grant(mini):
    assert mini.put(POLICY, headers=key(), json={"preview_token": "forged"}).status_code == 404
