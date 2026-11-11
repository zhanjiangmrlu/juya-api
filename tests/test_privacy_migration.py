"""Privacy expansion preserves old consent rows and allows legacy writers."""

import os

import pytest
from alembic import command
from sqlalchemy import MetaData, create_engine, inspect, text

from .test_import_recovery_migrations import migration_config


@pytest.mark.parametrize("backend", ["sqlite", pytest.param("mysql", marks=pytest.mark.mysql)])
def test_privacy_migration_preserves_legacy_consents_and_matches_metadata(
    tmp_path, monkeypatch, backend
):
    url = (
        os.getenv("JUYA_TEST_DATABASE_URL")
        if backend == "mysql"
        else f"sqlite:///{tmp_path / 'privacy-migrate.db'}"
    )
    if not url:
        pytest.skip("Dedicated local MySQL required")
    engine = create_engine(url, hide_parameters=True)
    if backend == "mysql":
        assert engine.url.database == "juya_verify" and engine.url.host in {
            "localhost",
            "127.0.0.1",
            "::1",
        }
        metadata = MetaData()
        metadata.reflect(engine)
        metadata.drop_all(engine)
    config = migration_config(monkeypatch, url)
    command.upgrade(config, "0026")
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO users (id,app_id,openid_digest,nickname,profile_version,"
                "contact_version,registered_at,last_login_at,user_number) "
                "VALUES ('account','app','digest','learner',1,1,'2026-11-10','2026-11-10',1)"
            )
        )
        db.execute(
            text(
                "INSERT INTO consents (id,user_id,purpose,version,accepted_at) "
                "VALUES ('old','account','wechat_login','old','2026-11-10')"
            )
        )
    command.upgrade(config, "head")
    assert {"analytics_preferences", "analytics_event_receipts"} <= set(
        inspect(engine).get_table_names()
    )
    with engine.connect() as db:
        assert db.execute(
            text("SELECT version,confirmation_id FROM consents WHERE id='old'")
        ).one() == ("old", None)
        assert db.scalar(text("SELECT count(*) FROM analytics_preferences")) == 0
    command.stamp(config, "0026")
    command.upgrade(config, "head")
    command.check(config)
    engine.dispose()
