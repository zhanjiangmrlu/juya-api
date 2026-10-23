"""Additive deletion expansion retains historical staging and accepts older INSERT shapes."""

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


@pytest.mark.parametrize("dialect", ["sqlite", "mysql"])
def test_import_soft_delete_migration_preserves_history_and_old_inserts(
    tmp_path, monkeypatch, dialect
):
    url = (
        os.getenv("JUYA_TEST_DATABASE_URL")
        if dialect == "mysql"
        else "sqlite+pysqlite:///" + str(tmp_path / "batch-delete.db")
    )
    if not url:
        pytest.skip("Private MySQL migration target is not configured")
    engine = create_engine(url, hide_parameters=True)
    if dialect == "mysql":
        from juya_api.database import Base

        if engine.dialect.name != "mysql" or engine.url.database != "juya_verify":
            raise RuntimeError(
                "Refusing any database except the dedicated MySQL verification schema"
            )
        Base.metadata.drop_all(engine)
        with engine.begin() as db:
            db.execute(text("DROP TABLE IF EXISTS alembic_version"))
    monkeypatch.setenv("JUYA_DATABASE_URL", url)
    monkeypatch.delenv("JUYA_MIGRATION_DATABASE_URL", raising=False)
    config = Config("alembic.ini")
    command.upgrade(config, "0016")
    try:
        with engine.begin() as db:
            db.execute(
                text(
                    "INSERT INTO administrators (id, username, password_hash) "
                    "VALUES ('admin', 'fixture', 'fixture')"
                )
            )
            db.execute(
                text(
                    "INSERT INTO import_batches (id, admin_id, mode, created_at, updated_at) "
                    "VALUES ('existing', 'admin', 'docx', "
                    "'2026-10-17 08:00:00.123456', '2026-10-17 09:00:00.654321')"
                )
            )
            before = db.execute(text("SELECT * FROM import_batches")).mappings().one()
        command.upgrade(config, "head")
        columns = {col["name"]: col for col in inspect(engine).get_columns("import_batches")}
        assert "deleted_at" in columns
        assert columns["deleted_at"]["nullable"] is True
        with engine.begin() as db:
            after = dict(db.execute(text("SELECT * FROM import_batches")).mappings().one())
            assert after.pop("deleted_at") is None
            assert after == dict(before)
            db.execute(
                text(
                    "INSERT INTO import_batches (id, admin_id, mode, created_at) "
                    "VALUES ('old-image', 'admin', 'zip', '2026-10-17 10:00:00.123456')"
                )
            )
            assert (
                db.scalar(text("SELECT deleted_at FROM import_batches WHERE id='old-image'"))
                is None
            )
        command.check(config)
        command.downgrade(config, "0016")
        assert "deleted_at" not in {
            col["name"] for col in inspect(engine).get_columns("import_batches")
        }
        command.upgrade(config, "head")
        command.check(config)
    finally:
        engine.dispose()
