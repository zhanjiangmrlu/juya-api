"""Synthetic persistence coverage for independent registration/checkin and overview rules."""

from datetime import UTC, date, datetime

import pytest

from juya_api.learning_models import Checkin

from .content_helpers import draft, key, publish
from .test_auth import login


@pytest.mark.parametrize(
    ("registered", "checkin", "expected"),
    [
        ("all", "all", {"today-checked", "today-unchecked", "old-checked", "old-unchecked"}),
        ("all", "checked", {"today-checked", "old-checked"}),
        ("all", "unchecked", {"today-unchecked", "old-unchecked"}),
        ("today", "all", {"today-checked", "today-unchecked"}),
        ("today", "checked", {"today-checked"}),
        ("today", "unchecked", {"today-unchecked"}),
    ],
)
def test_registration_and_checkin_filters_intersect(system, admin, registered, checkin, expected):
    """Four first-registration/checkin combinations remain independent for all six filters."""
    identities = {}
    for name in ("old-checked", "old-unchecked", "today-checked", "today-unchecked"):
        system["time"][0] = datetime(2026, 10, 16 if name.startswith("old") else 17, 8, tzinfo=UTC)
        response = login(system["mini"], code=name + ":first", key="register-" + name)
        assert response.status_code == 200, response.text
        identities[response.json()["user"]["id"]] = name
    with system["sessions"].begin() as db:
        for user_id, name in identities.items():
            # Only today's true Checkin facts participate; old unchecked users have a prior day.
            day = date(2026, 10, 17 if name.endswith("-checked") else 16)
            db.add(Checkin(user_id=user_id, date=day, accepted_at=system["time"][0]))
    response = admin.get(
        "/api/admin/v1/users", params={"registered": registered, "checkin": checkin}
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["statistical_date"] == "2026-10-17"
    assert result["total"] == len(expected)
    assert {identities[item["id"]] for item in result["items"]} == expected
    searched = admin.get(
        "/api/admin/v1/users",
        params={"search": "definitely-not-a-user", "registered": registered, "checkin": checkin},
    ).json()
    assert searched["total"] == 0


def test_first_registration_uses_beijing_midnight_and_relogin_does_not_move_it(system, admin):
    """UTC15:59:59 belongs to yesterday after UTC16:00:00; A05 and A07 agree."""
    client = system["mini"]
    system["time"][0] = datetime(2026, 10, 21, 15, 59, 59, tzinfo=UTC)
    session = admin.post(
        "/api/admin/v1/auth/login", json={"username": "admin", "password": "correct-test-password"}
    )
    assert session.status_code == 200, session.text
    admin.headers["X-CSRF-Token"] = session.json()["csrf_token"]
    before = login(client, code="before:first", key="register-before-midnight").json()["user"]
    yesterday = admin.get("/api/admin/v1/statistics").json()
    assert yesterday["statistical_date"] == "2026-10-21"
    assert yesterday["user_count"] == yesterday["new_users_today"] == 1
    system["time"][0] = datetime(2026, 10, 21, 16, 0, 0, tzinfo=UTC)
    empty_today = admin.get("/api/admin/v1/statistics").json()
    assert empty_today["statistical_date"] == "2026-10-22"
    assert empty_today["new_users_today"] == 0
    assert admin.get("/api/admin/v1/users?registered=today").json()["total"] == 0
    after = login(client, code="after:first", key="register-at-midnight").json()["user"]
    replay = login(client, code="before:second", key="relogin-after-midnight").json()["user"]
    assert replay["id"] == before["id"]
    assert replay["registered_at"] == before["registered_at"]
    assert replay["last_login_at"] != before["last_login_at"]
    today = admin.get("/api/admin/v1/statistics").json()
    assert today["user_count"] == 2  # excludes the synthetic administrator
    assert today["new_users_today"] == 1
    listing = admin.get("/api/admin/v1/users?registered=today&checkin=all").json()
    assert listing["statistical_date"] == today["statistical_date"]
    assert listing["total"] == today["new_users_today"]
    assert [item["id"] for item in listing["items"]] == [after["id"]]
    assert all(
        item["phone"] is None and item["wechat_contact"] is None for item in listing["items"]
    )
    assert listing["items"][0]["statistics"]["completed_cards"] == 0
    assert yesterday["updated_at"] != today["updated_at"]


def test_overview_counts_current_published_cards_once_through_lifecycle(admin):
    """Drafts do not count; new versions, offline and delete track current publication state."""

    def count(expected):
        overview = admin.get("/api/admin/v1/statistics").json()
        listing = admin.get("/api/admin/v1/cards?status=published").json()
        assert overview["published_card_count"] == listing["total"] == expected

    count(0)
    card = draft(admin)
    count(0)
    live = publish(admin, card)
    count(1)
    saved = admin.put(
        f"/api/admin/v1/cards/{card['id']}",
        headers=key(),
        json={"revision": live["draft_revision"], "content": dict(card["content"], name="新版")},
    )
    assert saved.status_code == 200, saved.text
    count(1)
    live = publish(admin, saved.json())
    count(1)
    offline = admin.post(
        f"/api/admin/v1/cards/{card['id']}/offline",
        headers=key(),
        json={"revision": live["draft_revision"]},
    )
    assert offline.status_code == 200, offline.text
    count(0)
    live = publish(admin, offline.json())
    count(1)
    removed = admin.request(
        "DELETE",
        f"/api/admin/v1/cards/{card['id']}",
        headers=key(),
        json={"revision": live["draft_revision"]},
    )
    assert removed.status_code == 200, removed.text
    count(0)
