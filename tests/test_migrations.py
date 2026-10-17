import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


@pytest.mark.mysql
@pytest.mark.skipif(
    not os.getenv("JUYA_TEST_DATABASE_URL"), reason="Fresh MySQL migration verification"
)
def test_fresh_migration_creates_empty_business_tables(monkeypatch):
    from juya_api.database import Base

    url = os.environ["JUYA_TEST_DATABASE_URL"]
    engine = create_engine(url)
    if engine.url.database != "juya_verify":
        raise RuntimeError("Migration tests require the dedicated verification database")
    Base.metadata.drop_all(engine)
    with engine.begin() as db:
        db.execute(text("DROP TABLE IF EXISTS alembic_version"))
    monkeypatch.setenv("JUYA_DATABASE_URL", url)
    monkeypatch.delenv("JUYA_MIGRATION_DATABASE_URL", raising=False)
    command.upgrade(Config("alembic.ini"), "head")
    assert {"users", "administrators", "mini_sessions", "admin_sessions"} <= set(
        inspect(engine).get_table_names()
    )
    with engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM users")) == 0
        assert db.scalar(text("SELECT count(*) FROM administrators")) == 0
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0001"
    engine.dispose()
