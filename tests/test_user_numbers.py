"""Stable human-facing user codes without replacing UUID ownership or navigation."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from .content_helpers import key
from .test_auth import login


def test_user_codes_stay_fixed_across_logins_searches_and_feedback(admin, mini):
    alice = mini.get("/api/mini/v1/me").json()["id"]
    first = admin.get("/api/admin/v1/users").json()["items"][0]
    assert first["id"] == alice
    assert first["user_code"] == "Juya001"
    bob = login(mini, code="bob:first", key="number-bob-login-0001").json()["user"]["id"]
    login(mini, code="alice:again", key="number-alice-login-0002")
    listing = admin.get("/api/admin/v1/users").json()
    assert {row["id"]: row["user_code"] for row in listing["items"]} == {
        alice: "Juya001",
        bob: "Juya002",
    }
    assert admin.get(f"/api/admin/v1/users/{alice}").json()["user_code"] == "Juya001"
    for query in ["Juya001", "juya001", alice]:
        result = admin.get("/api/admin/v1/users", params={"search": query}).json()
        assert result["total"] == 1
        assert result["items"][0]["id"] == alice
    feedback = mini.post(
        "/api/mini/v1/feedback",
        headers=key(),
        json={"category": "function", "source": "profile", "text": "编号显示问题"},
    )
    assert feedback.status_code == 201, feedback.text
    detail = feedback.json()
    assert detail["user_id"] == alice
    assert detail["user_code"] == "Juya001"
    rows = admin.get("/api/admin/v1/feedback", params={"search": "jUyA001"}).json()
    assert rows["total"] == 1
    assert rows["items"][0]["id"] == detail["id"]
    assert rows["items"][0]["user_code"] == "Juya001"
    assert admin.get(f"/api/admin/v1/feedback/{detail['id']}").json()["user_code"] == "Juya001"
    assert (
        admin.get("/api/admin/v1/users", params={"search": "Juya" + "9" * 100}).json()["total"] == 0
    )


def test_user_numbers_continue_past_three_digits_and_ignore_replayed_login(system, admin, mini):
    from juya_api.content_models import SettingCounter

    with system["sessions"].begin() as db:
        counter = db.get(SettingCounter, "user_number")
        assert counter is not None
        counter.value = 999
    response = login(mini, code="bob:first", key="number-bob-replay-0001")
    assert response.status_code == 200
    assert login(mini, code="bob:first", key="number-bob-replay-0001").json() == response.json()
    uid = response.json()["user"]["id"]
    assert admin.get(f"/api/admin/v1/users/{uid}").json()["user_code"] == "Juya1000"
    login(mini, code="bob:second", key="number-bob-next-000002")
    with system["sessions"]() as db:
        assert db.get(SettingCounter, "user_number").value == 1000


@pytest.mark.parametrize("action", ["create", "message", "admin-message"])
@pytest.mark.parametrize("replay_path", ["fast", "locked"])
def test_old_feedback_receipts_gain_user_code_without_repeating_the_write(
    system, admin, mini, monkeypatch, action, replay_path
):
    """Upgrade response shape on either replay path without rewriting a historical receipt."""
    import json

    from juya_api import feedback_api
    from juya_api.content_models import Operation
    from juya_api.security import decrypt, digest, encrypt

    original_headers = key()
    original_body = {"category": "function", "source": "profile", "text": "旧反馈"}
    created = mini.post("/api/mini/v1/feedback", headers=original_headers, json=original_body)
    assert created.status_code == 201
    feedback_id = created.json()["id"]
    if action == "create":
        client, path, body, headers, first = (
            mini,
            "/api/mini/v1/feedback",
            original_body,
            original_headers,
            created,
        )
    else:
        client = admin if action == "admin-message" else mini
        role = "admin" if action == "admin-message" else "mini"
        path, body, headers = (
            f"/api/{role}/v1/feedback/{feedback_id}/messages",
            {"text": "旧补充"},
            key(),
        )
        first = client.post(path, headers=headers, json=body)
        assert first.status_code == 200
    expected = first.json()
    with system["sessions"].begin() as db:
        receipt = db.scalar(
            select(Operation).where(Operation.key_digest == digest(headers["Idempotency-Key"]))
        )
        assert receipt is not None
        previous = json.loads(decrypt(system["settings"], receipt.result))
        previous.pop("user_code")
        old_cipher = encrypt(system["settings"], json.dumps(previous))
        receipt.result = old_cipher
    if replay_path == "locked":
        monkeypatch.setattr(feedback_api, "previous_result", lambda *args, **kwargs: None)
    repeated = client.post(path, headers=headers, json=body)
    assert repeated.status_code == first.status_code, repeated.text
    assert repeated.json() == expected
    timeline = admin.get(f"/api/admin/v1/feedback/{feedback_id}").json()
    assert timeline["latest_event_id"] == expected["latest_event_id"]
    with system["sessions"]() as db:
        receipt = db.scalar(
            select(Operation).where(Operation.key_digest == digest(headers["Idempotency-Key"]))
        )
        assert receipt.result == old_cipher


@pytest.mark.mysql
def test_concurrent_new_identities_get_unique_consecutive_numbers(system, admin):
    if system["engine"].dialect.name != "mysql":
        pytest.skip("Dedicated real MySQL required")
    barrier = Barrier(6)

    def attempt(index):
        with TestClient(system["mini"].app, base_url="https://testserver") as client:
            barrier.wait()
            return login(client, code=f"number-{index}:first", key=f"number-concurrent-{index:04d}")

    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(attempt, range(6)))
    assert [response.status_code for response in responses] == [200] * 6
    rows = admin.get("/api/admin/v1/users").json()["items"]
    assert {row["user_code"] for row in rows} == {f"Juya{number:03d}" for number in range(1, 7)}
    from juya_api.models import User

    with system["sessions"]() as db:
        assert sorted(db.scalars(select(User.user_number))) == [1, 2, 3, 4, 5, 6]
