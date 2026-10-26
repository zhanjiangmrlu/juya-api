"""Expand0018 preserves old facts and matches the runtime ORM on a real local DB."""

from alembic import command
from sqlalchemy import create_engine, inspect, text

from .test_import_recovery_migrations import migration_config


def test_0018_expands_without_granting_existing_users_and_can_be_reapplied(tmp_path, monkeypatch):
    url = "sqlite+pysqlite:///" + str(tmp_path / "access-upgrade.db")
    config = migration_config(monkeypatch, url)
    command.upgrade(config, "0017")
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO users (id,app_id,openid_digest,nickname,registered_at,last_login_at,"
                "profile_version,contact_version) VALUES "
                "('old','app','digest','学习者','2026-10-01','2026-10-01',1,1)"
            )
        )
    command.upgrade(config, "0018")
    with engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM users")) == 1
        assert db.scalar(text("SELECT count(*) FROM learning_authorizations")) == 0
        assert db.scalar(text("SELECT count(*) FROM learning_free_policy")) == 0
        assert (
            db.scalar(text("SELECT value FROM setting_counters WHERE name='schema_contract'")) == 1
        )
    command.upgrade(config, "head")
    command.check(config)
    command.downgrade(config, "0017")
    assert "learning_authorizations" not in inspect(engine).get_table_names()
    command.upgrade(config, "0018")
    command.upgrade(config, "head")
    command.check(config)
    engine.dispose()
