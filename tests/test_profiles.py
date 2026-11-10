import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from juya_api.content_models import Operation
from juya_api.models import LoginOperation, User
from juya_api.security import digest, encrypt, fingerprint, lookup

from .content_helpers import key, picture

RETIRED = {"phone", "wechat_contact", "phone_source", "wechat_source", "contact_version"}


@pytest.mark.parametrize("body", [{}, {"phone": "13812345678"}, {"wechat_contact": "legacy_name"}])
def test_contact_writes_are_gone_without_body_or_key_validation(system, mini, body):
    response = mini.patch("/api/mini/v1/me/contact", json=body)
    assert response.status_code == 410
    assert response.json()["error"]["code"] == "contact_collection_disabled"
    assert mini.patch("/api/mini/v1/me/contact", content="invalid-json").status_code == 410
    with system["sessions"]() as db:
        assert db.scalar(select(User)).phone_cipher is None
        assert db.scalar(select(Operation).where(Operation.action == "contact.save")) is None


def test_legacy_contacts_are_neither_returned_nor_searched(system, mini, admin):
    profile = mini.get("/api/mini/v1/me").json()
    with system["sessions"].begin() as db:
        user = db.get(User, profile["id"])
        user.phone_cipher = encrypt(system["settings"], "13812345678")
        user.phone_digest = lookup(system["settings"], "contact:phone", "13812345678")
    for result in [
        mini.get("/api/mini/v1/me").json(),
        admin.get("/api/admin/v1/users").json()["items"][0],
        admin.get("/api/admin/v1/users/" + profile["id"]).json(),
    ]:
        assert not RETIRED.intersection(result)
    assert admin.get("/api/admin/v1/users?search=13812345678").json()["total"] == 0
    assert admin.get("/api/admin/v1/users").json()["total"] == 1


@pytest.mark.parametrize("action", ["contact.save", "profile.save"])
def test_old_write_receipts_do_not_leak_contacts(system, mini, action):
    profile = mini.get("/api/mini/v1/me").json()
    payload = {"version": 1, "nickname": "学习者"}
    scope = "mini:" + profile["id"]
    with system["sessions"].begin() as db:
        db.add(
            Operation(
                scope=scope,
                key_digest=digest("legacy-receipt-00001"),
                action=action,
                fingerprint=lookup(
                    system["settings"],
                    "operation:" + scope,
                    fingerprint({"action": action, "payload": payload}),
                ),
                result=encrypt(
                    system["settings"],
                    json.dumps({**profile, "phone": "13812345678", "contact_version": 2}),
                ),
                accepted_at=system["time"][0],
            )
        )
    result = mini.get("/api/mini/v1/operations/legacy-receipt-00001")
    if action == "contact.save":
        assert result.status_code == 410
    else:
        assert not RETIRED.intersection(result.json()["result"])
        saved = mini.patch(
            "/api/mini/v1/me/profile",
            headers={"Idempotency-Key": "legacy-receipt-00001"},
            json=payload,
        )
        assert saved.status_code == 200
        assert not RETIRED.intersection(saved.json())


def test_login_replay_strips_legacy_profile(system, mini):
    with system["sessions"].begin() as db:
        row = db.scalar(select(LoginOperation))
        from juya_api.security import decrypt

        value = json.loads(decrypt(system["settings"], row.result_cipher))
        value["user"]["phone"] = "13812345678"
        row.result_cipher = encrypt(system["settings"], json.dumps(value))
    response = mini.post(
        "/api/mini/v1/auth/wechat",
        headers={"Idempotency-Key": "login-alice-first-0001"},
        json={"code": "alice:first", "consent_version": "2026-10-17", "consent": True},
    )
    assert response.status_code == 200
    assert not RETIRED.intersection(response.json()["user"])


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


def test_contact_retirement_keeps_authentication_and_rejects_profile_bypass(system, mini):
    assert system["admin"].patch("/api/mini/v1/me/contact", json={}).status_code == 404
    with TestClient(mini.app, base_url="https://testserver") as guest:
        assert guest.patch("/api/mini/v1/me/contact", json={}).status_code == 401
    response = mini.patch(
        "/api/mini/v1/me/profile", headers=key(), json={"version": 1, "phone": "13812345678"}
    )
    assert response.status_code == 422
    assert "13812345678" not in response.text


def test_cleanup_uses_real_database_and_keeps_stable_profile(system, mini):
    from juya_api.contact_cleanup import clean_contact_data

    before = mini.get("/api/mini/v1/me").json()
    with system["sessions"].begin() as db:
        user = db.get(User, before["id"])
        user.phone_cipher = encrypt(system["settings"], "13812345678")
        user.phone_digest = "legacy-digest"
        user.phone_source = "user_entered_unverified"
    preview = clean_contact_data(system["sessions"], system["settings"])
    assert preview["users_cleared"] == 1
    with system["sessions"]() as db:
        assert db.get(User, before["id"]).phone_cipher is not None
    result = clean_contact_data(system["sessions"], system["settings"], apply=True)
    assert result["status"] == "complete"
    assert result["users_cleared"] == 1
    with system["sessions"]() as db:
        assert db.get(User, before["id"]).phone_cipher is None
    assert mini.get("/api/mini/v1/me").json() == before
    assert (
        clean_contact_data(system["sessions"], system["settings"], apply=True)["users_cleared"] == 0
    )
