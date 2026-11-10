"""Database-visible documentation must preserve every non-comment schema attribute."""

import importlib.util
import os
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import MetaData, create_engine, event, inspect, text

from tests.test_import_recovery_migrations import migration_config


def migration():
    path = Path("migrations/versions/0025_database_comments.py")
    assert path.exists(), "Missing database comments migration"
    spec = importlib.util.spec_from_file_location("comments_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_comment_migration_is_complete_and_frozen():
    from juya_api import (  # noqa: F401
        access_models,
        admin_action_models,
        content_models,
        discovery_models,
        feedback_models,
        import_models,
        job_models,
        learning_models,
        listening_models,
        models,
        pronunciation_models,
        publication_models,
    )
    from juya_api.database import Base

    comments = migration().COMMENTS
    assert set(comments) == (
        set(Base.metadata.tables)
        - {"card_study_note_versions", "analytics_preferences", "analytics_event_receipts"}
    ) | {"alembic_version"}
    for name, table in Base.metadata.tables.items():
        if name in {
            "card_study_note_versions",
            "analytics_preferences",
            "analytics_event_receipts",
        }:
            continue  # New structure/comment coverage lives in migration 0026.
        assert comments[name]["table"] == table.comment
        assert comments[name]["columns"] == {
            c.name: c.comment
            for c in table.columns
            if c.name
            not in {
                "study_note",
                "study_note_version_id",
                "current_study_note_version_id",
            }
            and not (
                name == "consents"
                and c.name in {"confirmation_id", "source", "client_confirmed_at"}
            )
        }


def test_sqlite_comment_migration_leaves_data_untouched():
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    module = migration()
    engine = create_engine("sqlite://")
    with engine.begin() as db:
        db.execute(text("CREATE TABLE keep_me(id INTEGER PRIMARY KEY, value TEXT)"))
        db.execute(text("INSERT INTO keep_me VALUES (1, '原始内容')"))
        with Operations.context(MigrationContext.configure(db)):
            module.upgrade()
        assert db.execute(text("SELECT * FROM keep_me")).all() == [(1, "原始内容")]


@pytest.fixture
def mysql_schema(monkeypatch):
    url = os.getenv("JUYA_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Dedicated local MySQL required")
    engine = create_engine(url, hide_parameters=True)
    assert engine.url.database == "juya_verify"
    assert engine.url.host in {"127.0.0.1", "localhost", "::1"}
    metadata = MetaData()
    metadata.reflect(engine)
    metadata.drop_all(engine)
    config = migration_config(monkeypatch, url)
    command.upgrade(config, "0024")
    yield engine, config
    engine.dispose()


def column_attributes(db):
    return db.execute(
        text(
            "SELECT TABLE_NAME,COLUMN_NAME,ORDINAL_POSITION,COLUMN_DEFAULT,"
            "IS_NULLABLE,DATA_TYPE,CHARACTER_MAXIMUM_LENGTH,NUMERIC_PRECISION,NUMERIC_SCALE,"
            "DATETIME_PRECISION,CHARACTER_SET_NAME,COLLATION_NAME,COLUMN_TYPE,COLUMN_KEY,EXTRA "
            "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
            "ORDER BY TABLE_NAME,ORDINAL_POSITION"
        )
    ).all()


@pytest.mark.mysql
def test_mysql_upgrade_preserves_definitions_and_data_and_resumes(mysql_schema):
    engine, config = mysql_schema
    with engine.begin() as db:
        db.execute(text("INSERT INTO administrators VALUES ('keep','原管理员','hash')"))
        before = column_attributes(db)
    module = migration()
    altered = []

    def interrupt(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("ALTER TABLE"):
            assert "ALGORITHM=INPLACE, LOCK=NONE" in statement
            altered.append(statement)
            if len(altered) == 2:
                raise RuntimeError("simulated interruption")

    event.listen(engine, "before_cursor_execute", interrupt)
    # Run against this connection so interruption observes actual committed MySQL DDL.
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with (
        engine.connect() as db,
        Operations.context(MigrationContext.configure(db)),
        pytest.raises(RuntimeError, match="simulated interruption"),
    ):
        module.upgrade()
    event.remove(engine, "before_cursor_execute", interrupt)
    command.upgrade(config, "0025")
    command.upgrade(config, "0025")
    with engine.connect() as db:
        assert column_attributes(db) == before
        assert db.execute(text("SELECT * FROM administrators")).all() == [
            ("keep", "原管理员", "hash")
        ]
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0025"
        assert (
            db.scalar(
                text(
                    "SELECT COUNT(*) FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA=DATABASE() AND COLUMN_COMMENT=''"
                )
            )
            == 0
        )
        assert (
            db.scalar(
                text(
                    "SELECT COUNT(*) FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_COMMENT=''"
                )
            )
            == 0
        )
    command.upgrade(config, "head")
    command.check(config)


@pytest.mark.mysql
def test_mysql_lock_timeout_does_not_change_locked_table(mysql_schema):
    import time

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy.exc import OperationalError

    engine, _ = mysql_schema
    with engine.connect() as holder, engine.connect() as db:
        holder.execute(text("SELECT * FROM administrators"))
        started = time.monotonic()
        with (
            Operations.context(MigrationContext.configure(db)),
            pytest.raises(OperationalError) as error,
        ):
            migration().upgrade()
        assert error.value.orig.args[0] == 1205
        assert time.monotonic() - started < 9
        holder.rollback()
    assert not inspect(engine).get_table_comment("administrators")["text"]
