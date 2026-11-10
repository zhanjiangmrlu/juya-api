"""Add PDF publication references without rewriting body versions or legacy drafts."""

import os

import pytest
from alembic import command
from sqlalchemy import MetaData, create_engine, inspect, text

from .test_import_recovery_migrations import migration_config


@pytest.mark.parametrize("backend", ["sqlite", pytest.param("mysql", marks=pytest.mark.mysql)])
def test_additive_study_note_migration_preserves_legacy_body_and_contract(
    tmp_path, monkeypatch, backend
):
    url = (
        os.getenv("JUYA_TEST_DATABASE_URL")
        if backend == "mysql"
        else f"sqlite:///{tmp_path / 'migrate.db'}"
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
    command.upgrade(config, "0025")
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO cards (id,status,sort_order,created_at,is_free,free_revision) "
                "VALUES ('keep','draft',7,'2026-11-06',0,1)"
            )
        )
        db.execute(
            text(
                "INSERT INTO card_drafts (card_id,revision,payload,updated_at) "
                "VALUES ('keep',4,'{}','2026-11-06')"
            )
        )
    command.upgrade(config, "head")
    assert "card_study_note_versions" in inspect(engine).get_table_names()
    with engine.connect() as db:
        assert db.execute(
            text(
                "SELECT sort_order,current_version_id,current_study_note_version_id "
                "FROM cards WHERE id='keep'"
            )
        ).one() == (7, None, None)
        assert db.execute(
            text("SELECT revision,study_note FROM card_drafts WHERE card_id='keep'")
        ).one() == (4, None)
        assert (
            db.scalar(text("SELECT value FROM setting_counters WHERE name='schema_contract'")) == 3
        )
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0027"
    # A stamp retry cannot duplicate version storage or rewrite legacy draft/body identity.
    command.stamp(config, "0025")
    command.upgrade(config, "head")
    command.check(config)
    engine.dispose()
