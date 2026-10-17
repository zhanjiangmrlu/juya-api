"""A role image must match its API; readiness rejects incomplete or incompatible schemas."""

import pytest
from sqlalchemy import text


def test_readiness_requires_migration_and_allows_only_compatible_expansion(system):
    from juya_api.content_models import SettingCounter

    client = system["admin"]
    sessions = system["sessions"]
    with sessions.begin() as db:
        db.execute(text("DROP TABLE IF EXISTS alembic_version"))
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 503
    with sessions.begin() as db:
        db.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        db.execute(text("INSERT INTO alembic_version VALUES ('0008')"))
        db.merge(SettingCounter(name="schema_contract", value=1))
    assert client.get("/health/ready").status_code == 503
    with sessions.begin() as db:
        db.execute(text("UPDATE alembic_version SET version_num='0011'"))
    assert client.get("/health/ready").status_code == 200
    # A newer additive migration remains usable without restarting the other API.
    with sessions.begin() as db:
        db.execute(text("UPDATE alembic_version SET version_num='0012'"))
    assert client.get("/health/ready").status_code == 200
    assert system["mini"].get("/health/ready").status_code == 200
    with sessions.begin() as db:
        db.get(SettingCounter, "schema_contract").value = 2
    assert client.get("/health/ready").status_code == 503
    assert system["mini"].get("/health/ready").status_code == 503


def test_role_image_cannot_start_the_other_api_or_other_role_worker(system):
    from juya_api.admin import create_app as admin_app
    from juya_api.config import Settings
    from juya_api.mini import create_app as mini_app

    values = system["settings"].model_dump()
    admin_settings = Settings(**{**values, "image_role": "admin"})
    assert admin_app(admin_settings, sessions=system["sessions"]).state.role == "admin"
    with pytest.raises(ValueError, match="image role"):
        mini_app(admin_settings, sessions=system["sessions"])
    with pytest.raises(ValueError, match="Worker role"):
        Settings(**{**values, "image_role": "admin", "worker_role": "mini"})


def test_runtime_preflight_rejects_cross_environment_dependencies(system):
    import importlib.util
    from pathlib import Path

    from juya_api.config import Settings

    path = Path(__file__).resolve().parents[1] / "deploy/runtime-preflight.py"
    spec = importlib.util.spec_from_file_location("runtime_preflight", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    values = {
        **system["settings"].model_dump(),
        "image_role": "admin",
        "database_url": "mysql+pymysql://juya_test_app:fake@mysql/juya_test",
        "redis_url": "redis://:fake@redis-test:6379/0",
        "storage_backend": "oss",
        "oss_bucket": "test-private",
        "oss_region": "cn-shenzhen",
        "oss_endpoint": "https://oss-cn-shenzhen.aliyuncs.com",
        "oss_access_key_id": "test-id",
        "oss_access_key_secret": "test-secret",
        "wechat_app_secret": "fake-wechat-secret",
        "tts_secret_id": "fake-tts-id",
        "tts_secret_key": "fake-tts-key",
    }
    module.check_target(Settings(**values), "test", "admin", "test-private")
    for key, wrong in [
        ("database_url", "mysql+pymysql://juya_production_app:fake@mysql/juya_production"),
        ("database_url", "mysql+pymysql://root:fake@mysql/juya_test"),
        ("redis_url", "redis://:fake@redis-production:6379/0"),
        ("oss_bucket", "production-private"),
        ("storage_backend", "local"),
        ("image_role", "mini"),
    ]:
        with pytest.raises(ValueError):
            module.check_target(Settings(**{**values, key: wrong}), "test", "admin", "test-private")


@pytest.mark.parametrize("role,expected", [("admin", 1), ("mini", 0)])
def test_worker_probe_checks_the_selected_roles_schema(system, monkeypatch, role, expected):
    import importlib.util
    from pathlib import Path

    from redis import Redis

    from juya_api import config, database
    from juya_api.content_models import SettingCounter

    with system["sessions"].begin() as db:
        db.execute(text("DROP TABLE IF EXISTS alembic_version"))
        db.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        db.execute(text("INSERT INTO alembic_version VALUES ('0010')"))
        db.merge(SettingCounter(name="schema_contract", value=1))
    settings = config.Settings(
        **{**system["settings"].model_dump(), "image_role": role, "worker_role": role}
    )

    class Broker:
        def ping(self):
            return True

        def close(self):
            pass

    monkeypatch.setattr(Redis, "from_url", lambda *args, **kwargs: Broker())
    monkeypatch.setattr(config, "Settings", lambda: settings)
    monkeypatch.setattr(
        database, "make_database", lambda settings: (system["engine"], system["sessions"])
    )
    monkeypatch.setattr("sys.argv", ["container-health.py", "worker"])
    path = Path(__file__).resolve().parents[1] / "deploy/container-health.py"
    spec = importlib.util.spec_from_file_location("worker_health", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main() == expected
