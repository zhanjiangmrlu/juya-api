from fastapi.testclient import TestClient
from sqlalchemy import text

from .content_helpers import key, picture


def test_empty_contacts_are_a_normal_account_and_do_not_require_a_save(mini, admin):
    profile = mini.get("/api/mini/v1/me").json()
    assert profile["phone"] is None
    listing = admin.get("/api/admin/v1/users").json()
    assert listing["total"] == 1
    assert listing["items"][0]["statistics"]["completed_cards"] == 0
    assert admin.get("/api/admin/v1/statistics").json()["user_count"] == 1


def test_contacts_are_atomic_encrypted_and_searchable_only_to_admin(system, mini, admin):
    response = mini.patch(
        "/api/mini/v1/me/contact",
        headers=key(),
        json={
            "version": 1,
            "phone": "13812345678",
            "wechat_contact": "juya_english",
            "consent_version": "2026-10-17",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["phone_source"] == "user_entered_unverified"
    assert admin.get("/api/admin/v1/users", params={"search": "13812345678"}).json()["total"] == 1
    with system["sessions"]() as db:
        stored = str(
            db.execute(
                text("SELECT phone_cipher,wechat_cipher,phone_digest,wechat_digest FROM users")
            ).all()
        )
        operations = str(db.execute(text("SELECT result FROM operations")).all())
    assert "13812345678" not in stored + operations
    assert "juya_english" not in stored + operations


def test_existing_contact_cannot_be_cleared_and_bad_second_field_rolls_back_first(mini):
    assert (
        mini.patch(
            "/api/mini/v1/me/contact",
            headers=key(),
            json={"version": 1, "phone": "13812345678", "consent_version": "2026-10-17"},
        ).status_code
        == 200
    )
    assert (
        mini.patch(
            "/api/mini/v1/me/contact",
            headers=key(),
            json={"version": 2, "phone": "", "consent_version": "2026-10-17"},
        ).status_code
        == 422
    )
    assert (
        mini.patch(
            "/api/mini/v1/me/contact",
            headers=key(),
            json={
                "version": 2,
                "phone": "13912345678",
                "wechat_contact": "!",
                "consent_version": "2026-10-17",
            },
        ).status_code
        == 422
    )
    assert mini.get("/api/mini/v1/me").json()["phone"] == "13812345678"


def test_profile_and_contact_versions_are_separate_and_stale_writes_are_rejected(mini):
    assert (
        mini.patch(
            "/api/mini/v1/me/profile", headers=key(), json={"version": 1, "nickname": "新的学习者"}
        ).status_code
        == 200
    )
    assert (
        mini.patch(
            "/api/mini/v1/me/contact",
            headers=key(),
            json={"version": 1, "wechat_contact": "juya_english", "consent_version": "2026-10-17"},
        ).status_code
        == 200
    )
    assert (
        mini.patch(
            "/api/mini/v1/me/contact",
            headers=key(),
            json={"version": 1, "wechat_contact": "another_name", "consent_version": "2026-10-17"},
        ).status_code
        == 409
    )
    current = mini.get("/api/mini/v1/me").json()
    assert current["nickname"] == "新的学习者"
    assert current["wechat_contact"] == "juya_english"


def test_identical_contact_values_do_not_merge_two_wechat_identities(system, mini, admin):
    assert (
        mini.patch(
            "/api/mini/v1/me/contact",
            headers=key(),
            json={"version": 1, "phone": "13812345678", "consent_version": "2026-10-17"},
        ).status_code
        == 200
    )
    alice = mini.get("/api/mini/v1/me").json()["id"]
    with TestClient(mini.app, base_url="https://testserver") as bob:
        login = bob.post(
            "/api/mini/v1/auth/wechat",
            headers=key(),
            json={"code": "bob:first", "consent": True, "consent_version": "2026-10-17"},
        ).json()
        bob.headers["Authorization"] = "Bearer " + login["access_token"]
        assert (
            bob.patch(
                "/api/mini/v1/me/contact",
                headers=key(),
                json={"version": 1, "phone": "13812345678", "consent_version": "2026-10-17"},
            ).status_code
            == 200
        )
        assert bob.get("/api/mini/v1/me").json()["id"] != alice
    assert admin.get("/api/admin/v1/users", params={"search": "13812345678"}).json()["total"] == 2


def test_profile_change_does_not_modify_registration_or_create_new_users(mini, admin):
    before = mini.get("/api/mini/v1/me").json()
    result = mini.patch(
        "/api/mini/v1/me/profile", headers=key(), json={"version": 1, "nickname": "  "}
    )
    assert result.status_code == 200
    assert result.json()["nickname"] == "学习者"
    assert result.json()["registered_at"] == before["registered_at"]
    assert admin.get("/api/admin/v1/statistics").json()["new_users_today"] == 1


def test_admin_has_no_write_routes_for_user_contacts_or_grades(mini, admin):
    user_id = mini.get("/api/mini/v1/me").json()["id"]
    assert admin.patch(
        f"/api/admin/v1/users/{user_id}", headers=key(), json={"phone": "13812345678"}
    ).status_code in {404, 405}
    assert mini.get(f"/api/admin/v1/users/{user_id}").status_code == 404


def test_contact_retry_recovers_original_response_before_rejecting_stale_version(mini):
    headers = key()
    body = {"version": 1, "phone": "13812345678", "consent_version": "2026-10-17"}
    first = mini.patch("/api/mini/v1/me/contact", headers=headers, json=body)
    second = mini.patch("/api/mini/v1/me/contact", headers=headers, json=body)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    recovered = mini.get("/api/mini/v1/operations/" + headers["Idempotency-Key"])
    assert recovered.status_code == 200
    assert recovered.json()["result"] == first.json()


def test_avatar_is_explicitly_uploaded_saved_and_revoked_on_logout(mini):
    before = mini.get("/api/mini/v1/me").json()
    uploaded = mini.post(
        "/api/mini/v1/me/avatar",
        headers=key(),
        files={"file": ("avatar.png", picture(), "image/png")},
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["state"] == "processing"
    from .content_helpers import process_jobs

    process_jobs(mini)
    assert mini.get("/api/mini/v1/me").json()["avatar_id"] is None
    saved = mini.patch(
        "/api/mini/v1/me/profile",
        headers=key(),
        json={"version": 1, "avatar_id": uploaded.json()["id"]},
    )
    assert saved.status_code == 200
    assert saved.json()["registered_at"] == before["registered_at"]
    url = mini.get("/api/mini/v1/me/avatar-url").json()["url"]
    assert mini.get(url).status_code == 200
    assert mini.post("/api/mini/v1/auth/logout").status_code == 200
    assert mini.get(url).status_code == 401
