"""0028 adds only batch tables and preserves every existing row and column."""

import os

import pytest
from alembic import command
from sqlalchemy import MetaData, create_engine, inspect, text

from .test_import_recovery_migrations import migration_config


@pytest.mark.parametrize("backend", ["sqlite", pytest.param("mysql", marks=pytest.mark.mysql)])
def test_0028_preserves_old_table_snapshots_and_matches_metadata(tmp_path, monkeypatch, backend):
    url = (
        os.getenv("JUYA_TEST_DATABASE_URL")
        if backend == "mysql"
        else f"sqlite:///{tmp_path / 'batch.db'}"
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
    command.upgrade(config, "0027")
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO administrators (id,username,password_hash) "
                "VALUES ('admin','preserved','hash')"
            )
        )
    old = MetaData()
    old.reflect(engine)
    with engine.connect() as db:
        before = {
            t.name: list(db.execute(t.select()))
            for t in old.sorted_tables
            if t.name != "alembic_version"
        }
    command.upgrade(config, "head")
    assert set(inspect(engine).get_table_names()) - set(old.tables) == {
        "free_access_batches",
        "free_access_batch_items",
    }
    with engine.connect() as db:
        assert {
            t.name: list(db.execute(t.select()))
            for t in old.sorted_tables
            if t.name != "alembic_version"
        } == before
    command.check(config)
    engine.dispose()
