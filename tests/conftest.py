"""Real local SQL persistence; only the external WeChat exchange is substituted."""

import os
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def system(tmp_path):
    try:
        from juya_api.admin import create_app as admin_app
        from juya_api.auth import create_administrator
        from juya_api.config import Settings
        from juya_api.database import Base, make_database
        from juya_api.mini import create_app as mini_app
    except ImportError as exc:
        pytest.fail(f"The new independent API/authentication feature is missing: {exc}")

    settings = Settings(
        environment="test",
        database_url=os.getenv(
            "JUYA_TEST_DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'test.db'}"
        ),
        field_encryption_key="yK1Xc0sWCxUQxXvHPEgY46iVE1mW6BwJqHWSeg1oEJ4=",
        lookup_key="test-lookup-secret-with-at-least-32-characters",
        wechat_app_id="test-app",
        media_root=tmp_path / "media",
    )
    engine, sessions = make_database(settings)
    if engine.dialect.name == "mysql":
        if engine.url.database != "juya_verify":
            raise RuntimeError("Refusing to reset any database except juya_verify")
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with sessions.begin() as db:
        create_administrator(db, "admin", "correct-test-password")
    time = [datetime(2026, 10, 17, 8, 0, tzinfo=UTC)]

    class Wechat:
        calls = 0

        def exchange(self, code):
            self.calls += 1
            if code == "invalid":
                from juya_api.errors import DomainError

                raise DomainError(401, "wechat_failed", "登录暂未成功，请重试")
            return "openid-" + code.split(":")[0]

    gateway = Wechat()
    admin = admin_app(settings, sessions=sessions, clock=lambda: time[0])
    mini = mini_app(settings, sessions=sessions, clock=lambda: time[0], wechat=gateway)
    with (
        TestClient(admin, base_url="https://testserver") as a,
        TestClient(mini, base_url="https://testserver") as m,
    ):
        yield {
            "admin": a,
            "mini": m,
            "sessions": sessions,
            "settings": settings,
            "time": time,
            "wechat": gateway,
            "engine": engine,
        }
    engine.dispose()


@pytest.fixture
def admin(system):
    client = system["admin"]
    response = client.post(
        "/api/admin/v1/auth/login", json={"username": "admin", "password": "correct-test-password"}
    )
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return client


@pytest.fixture
def mini(system):
    client = system["mini"]
    response = client.post(
        "/api/mini/v1/auth/wechat",
        json={
            "code": "alice:first",
            "consent_version": "2026-10-17",
            "consent": True,
        },
        headers={"Idempotency-Key": "login-alice-first-0001"},
    )
    assert response.status_code == 200, response.text
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
    return client
