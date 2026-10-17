from fastapi.testclient import TestClient


def login(client, code="alice:first", key="login-attempt-00001", consent=True):
    return client.post(
        "/api/mini/v1/auth/wechat",
        json={
            "code": code,
            "consent": consent,
            "consent_version": "2026-10-17",
        },
        headers={"Idempotency-Key": key},
    )


def test_anonymous_access_does_not_create_a_user(system):
    assert system["mini"].get("/api/mini/v1/me").status_code == 401
    assert system["admin"].get("/api/admin/v1/auth/session").status_code == 401
    assert system["mini"].get("/api/admin/v1/users").status_code == 404
    assert system["admin"].get("/api/mini/v1/me").status_code == 404


def test_consent_is_required_before_wechat_exchange(system):
    response = login(system["mini"], consent=False)
    assert response.status_code == 422
    assert system["wechat"].calls == 0


def test_verified_identity_creates_one_contact_optional_account(system):
    client = system["mini"]
    first = login(client).json()
    second = login(client, code="alice:second", key="login-attempt-00002").json()
    assert first["user"]["id"] == second["user"]["id"]
    assert first["user"]["registered_at"] == second["user"]["registered_at"]
    assert first["user"]["nickname"] == "学习者"
    assert first["user"]["phone"] is None
    assert first["user"]["wechat_contact"] is None
    assert first["access_token"] != second["access_token"]
    assert "openid" not in str(first)
    assert "session_key" not in str(first)


def test_unknown_login_response_replays_without_redeeming_code_twice(system):
    first = login(system["mini"])
    second = login(system["mini"])
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert system["wechat"].calls == 1
    changed = login(system["mini"], code="bob:first")
    assert changed.status_code == 409


def test_invalid_wechat_code_does_not_issue_session(system):
    response = login(system["mini"], code="invalid")
    assert response.status_code == 401
    assert "access_token" not in response.json()
    assert login(system["mini"], code="invalid").status_code == 401


def test_logout_revokes_the_actual_server_session(mini):
    assert mini.get("/api/mini/v1/me").status_code == 200
    assert mini.post("/api/mini/v1/auth/logout").status_code == 200
    assert mini.get("/api/mini/v1/me").status_code == 401


def test_admin_bad_password_and_csrf_are_rejected(system, admin):
    client = system["admin"]
    bad = client.post(
        "/api/admin/v1/auth/login", json={"username": "admin", "password": "incorrect"}
    )
    assert bad.status_code == 401
    csrf = client.headers.pop("X-CSRF-Token")
    assert client.post("/api/admin/v1/auth/logout").status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    assert client.post("/api/admin/v1/auth/logout").status_code == 200
    assert client.get("/api/admin/v1/auth/session").status_code == 401


def test_credentials_cannot_cross_api_roles(system, mini, admin):
    token = mini.headers["Authorization"]
    with TestClient(system["admin"].app) as other:
        assert (
            other.get("/api/admin/v1/auth/session", headers={"Authorization": token}).status_code
            == 401
        )
    with TestClient(system["mini"].app) as other:
        other.cookies.update(admin.cookies)
        assert other.get("/api/mini/v1/me").status_code == 401


def test_validation_errors_do_not_echo_passwords(system):
    response = system["admin"].post(
        "/api/admin/v1/auth/login", json={"username": [], "password": "NEVER-ECHO-THIS-PASSWORD"}
    )
    assert response.status_code == 422
    assert "NEVER-ECHO" not in response.text


def test_admin_reload_recovers_csrf_for_the_existing_cookie(admin):
    response = admin.get("/api/admin/v1/auth/session")
    assert response.status_code == 200
    assert response.json()["csrf_token"] == admin.headers["X-CSRF-Token"]
