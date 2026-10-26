"""Backfill stable numbers deterministically without rewriting UUID references."""

import os

import pytest
from alembic import command
from sqlalchemy import MetaData, create_engine, text

from .test_import_recovery_migrations import migration_config


@pytest.mark.parametrize("backend", ["sqlite", pytest.param("mysql", marks=pytest.mark.mysql)])
def test_0019_numbers_existing_users_in_registration_order_and_survives_round_trip(
    tmp_path, monkeypatch, backend
):
    url = (
        os.getenv("JUYA_TEST_DATABASE_URL")
        if backend == "mysql"
        else "sqlite+pysqlite:///" + str(tmp_path / "user-numbers.db")
    )
    if not url:
        pytest.skip("Dedicated real MySQL required")
    engine = create_engine(url, hide_parameters=True)
    if backend == "mysql":
        if engine.dialect.name != "mysql" or engine.url.database != "juya_verify":
            raise RuntimeError("User number migration requires the dedicated verification database")
        metadata = MetaData()
        metadata.reflect(engine)
        metadata.drop_all(engine)
    config = migration_config(monkeypatch, url)
    command.upgrade(config, "0018")
    with engine.begin() as db:
        for uid, registered in [
            ("latest", "2026-10-25"),
            ("old-b", "2026-10-01"),
            ("old-a", "2026-10-01"),
        ]:
            db.execute(
                text(
                    "INSERT INTO users(id,app_id,openid_digest,nickname,"
                    "registered_at,last_login_at,"
                    "profile_version,contact_version) "
                    "VALUES (:uid,'app',:uid,'学习者',:day,:day,1,1)"
                ),
                {"uid": uid, "day": registered},
            )
        db.execute(
            text(
                "INSERT INTO checkins(user_id,date,accepted_at) "
                "VALUES ('old-a','2026-10-02','2026-10-02')"
            )
        )
    for _ in range(2):
        command.upgrade(config, "0019")
        command.upgrade(config, "head")
        with engine.connect() as db:
            assert dict(db.execute(text("SELECT id,user_number FROM users")).all()) == {
                "old-a": 1,
                "old-b": 2,
                "latest": 3,
            }
            assert (
                db.scalar(text("SELECT value FROM setting_counters WHERE name='user_number'")) == 3
            )
            assert db.scalar(text("SELECT user_id FROM checkins")) == "old-a"
        command.check(config)
        command.downgrade(config, "0018")
    engine.dispose()
