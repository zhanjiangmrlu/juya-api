import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from .content_helpers import draft, key, publish


def scene(admin):
    card = draft(admin)
    version = publish(admin, card)["current_version_id"]
    return card, version


def complete(mini, card, version, headers=None):
    return mini.post(
        f"/api/mini/v1/cards/{card['id']}/complete",
        headers=headers or key(),
        json={"version_id": version},
    )


def test_first_completion_updates_three_records_and_both_api_statistics(admin, mini):
    card, version = scene(admin)
    response = complete(mini, card, version)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["date"] == "2026-10-17"
    assert result["first_checkin_today"] is True
    assert result["statistics"]["completed_cards"] == 1
    assert result["statistics"]["total_checkin_days"] == 1
    assert result["statistics"]["current_streak"] == 1
    profile = mini.get("/api/mini/v1/me").json()
    detail = admin.get(f"/api/admin/v1/users/{profile['id']}").json()
    assert detail["statistics"] == mini.get("/api/mini/v1/me/statistics").json()
    assert mini.get("/api/mini/v1/me/learning-records").json()["total"] == 1
    assert mini.get("/api/mini/v1/me/checkins/2026-10-17").json()["total"] == 1


def test_same_card_and_different_cards_do_not_duplicate_daily_checkin(admin, mini):
    first, version = scene(admin)
    second, other_version = scene(admin)
    assert complete(mini, first, version).status_code == 200
    assert complete(mini, first, version).status_code == 200
    assert complete(mini, second, other_version).status_code == 200
    stats = mini.get("/api/mini/v1/me/statistics").json()
    assert stats["completed_cards"] == 2
    assert stats["today_completed_cards"] == 2
    assert stats["total_checkin_days"] == 1


def test_midnight_retry_retains_original_day_and_new_review_requires_new_operation(
    system, admin, mini
):
    card, version = scene(admin)
    system["time"][0] = datetime(2026, 10, 17, 15, 59, tzinfo=UTC)
    headers = key()
    first = complete(mini, card, version, headers)
    assert first.status_code == 200
    system["time"][0] = datetime(2026, 10, 17, 16, 1, tzinfo=UTC)
    replay = complete(mini, card, version, headers)
    assert replay.json() == first.json()
    stats = mini.get("/api/mini/v1/me/statistics").json()
    assert stats["date"] == "2026-10-18"
    assert stats["checked_in_today"] is False
    assert stats["current_streak"] == 1
    reviewed = complete(mini, card, version).json()
    assert reviewed["date"] == "2026-10-18"
    assert reviewed["statistics"]["completed_cards"] == 1
    assert reviewed["statistics"]["total_checkin_days"] == 2
    assert reviewed["statistics"]["current_streak"] == 2


def test_streak_is_preserved_until_a_whole_day_is_missed(system, admin, mini):
    card, version = scene(admin)
    for day in [17, 18, 20, 21]:
        system["time"][0] = datetime(2026, 10, day, 8, tzinfo=UTC)
        assert complete(mini, card, version).status_code == 200
    system["time"][0] = datetime(2026, 10, 22, 8, tzinfo=UTC)
    stats = mini.get("/api/mini/v1/me/statistics").json()
    assert stats["completed_cards"] == 1
    assert stats["total_checkin_days"] == 4
    assert stats["longest_streak"] == 2
    assert stats["current_streak"] == 2
    system["time"][0] += timedelta(days=1)
    assert mini.get("/api/mini/v1/me/statistics").json()["current_streak"] == 0


def test_browsing_and_favorites_do_not_count_as_learning(admin, mini):
    card, version = scene(admin)
    assert mini.get(f"/api/mini/v1/cards/{card['id']}").status_code == 200
    assert (
        mini.put(
            f"/api/mini/v1/cards/{card['id']}/favorite", headers=key(), json={"version_id": version}
        ).status_code
        == 200
    )
    assert mini.get("/api/mini/v1/me/statistics").json()["completed_cards"] == 0
    assert mini.get("/api/mini/v1/me/statistics").json()["total_checkin_days"] == 0
    assert mini.get("/api/mini/v1/favorites").json()["total"] == 1
    assert mini.get("/api/mini/v1/favorites").json()["items"][0]["favorited_at"] == (
        "2026-10-17T08:00:00.000000Z"
    )
    assert mini.delete(f"/api/mini/v1/favorites/{card['id']}", headers=key()).status_code == 200
    assert mini.get("/api/mini/v1/favorites").json()["total"] == 0


def test_deleted_cards_keep_history_but_never_expose_old_full_content(admin, mini):
    card, version = scene(admin)
    complete(mini, card, version)
    assert (
        admin.request(
            "DELETE", f"/api/admin/v1/cards/{card['id']}", headers=key(), json={"revision": 1}
        ).status_code
        == 200
    )
    assert mini.get("/api/mini/v1/me/statistics").json()["completed_cards"] == 1
    records = mini.get("/api/mini/v1/me/learning-records").json()
    assert records["items"] == []
    assert records["total"] == 0
    assert complete(mini, card, version).status_code == 410


def test_failure_during_checkin_insert_rolls_back_completion_and_daily_source(system, admin, mini):
    card, version = scene(admin)

    def fail_checkin(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT INTO CHECKINS"):
            raise RuntimeError("injected checkin persistence failure")

    event.listen(system["engine"], "before_cursor_execute", fail_checkin)
    try:
        with TestClient(
            mini.app, base_url="https://testserver", raise_server_exceptions=False
        ) as client:
            response = client.post(
                f"/api/mini/v1/cards/{card['id']}/complete",
                json={"version_id": version},
                headers={**key(), "Authorization": mini.headers["Authorization"]},
            )
            assert response.status_code == 500
    finally:
        event.remove(system["engine"], "before_cursor_execute", fail_checkin)
    assert mini.get("/api/mini/v1/me/statistics").json()["completed_cards"] == 0
    assert mini.get("/api/mini/v1/me/checkins").json()["total"] == 0
    assert complete(mini, card, version).status_code == 200


def test_database_commit_failure_is_not_acknowledged_as_learning_success(system, admin, mini):
    card, version = scene(admin)

    def fail_commit(connection):
        raise RuntimeError("injected transaction commit failure")

    event.listen(system["engine"], "commit", fail_commit)
    try:
        with TestClient(
            mini.app, base_url="https://testserver", raise_server_exceptions=False
        ) as client:
            response = client.post(
                f"/api/mini/v1/cards/{card['id']}/complete",
                json={"version_id": version},
                headers={**key(), "Authorization": mini.headers["Authorization"]},
            )
            assert response.status_code == 500
    finally:
        event.remove(system["engine"], "commit", fail_commit)
    assert mini.get("/api/mini/v1/me/statistics").json()["completed_cards"] == 0


@pytest.mark.mysql
@pytest.mark.skipif(not os.getenv("JUYA_TEST_DATABASE_URL"), reason="Real MySQL concurrency")
def test_concurrent_different_cards_have_two_completions_and_only_one_checkin(system, admin, mini):
    cards = [scene(admin), scene(admin)]
    barrier = Barrier(2)

    def finish(item):
        card, version = item
        with TestClient(mini.app, base_url="https://testserver") as client:
            client.headers["Authorization"] = mini.headers["Authorization"]
            barrier.wait()
            return complete(client, card, version)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(finish, cards))
    assert [r.status_code for r in responses] == [200, 200]
    stats = mini.get("/api/mini/v1/me/statistics").json()
    assert stats["completed_cards"] == 2
    assert stats["today_completed_cards"] == 2
    assert stats["total_checkin_days"] == 1
