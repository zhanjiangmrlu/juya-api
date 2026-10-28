"""0020 expands both dialects without rewriting scene/account/history facts."""

from datetime import datetime
from io import StringIO

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, create_engine, inspect, select, text


def test_listening_expansion_preserves_every_existing_table_row(tmp_path, monkeypatch):
    url = "sqlite+pysqlite:///" + str(tmp_path / "revision17.db")
    monkeypatch.setenv("JUYA_DATABASE_URL", url)
    monkeypatch.delenv("JUYA_MIGRATION_DATABASE_URL", raising=False)
    config = Config("alembic.ini")
    command.upgrade(config, "0019")
    engine = create_engine(url)
    old = MetaData()
    old.reflect(engine)
    now = datetime(2026, 10, 28, 0, 0, 0, 123456)
    with engine.begin() as db:
        db.execute(
            old.tables["users"]
            .insert()
            .values(
                id="existing-user",
                user_number=1,
                app_id="existing-app",
                openid_digest="existing-user",
                nickname="现有用户",
                profile_version=1,
                contact_version=1,
                registered_at=now,
                last_login_at=now,
            )
        )
        db.execute(
            old.tables["cards"]
            .insert()
            .values(
                id="existing-card",
                status="published",
                current_version_id="existing-version",
                sort_order=1,
                created_at=now,
            )
        )
        db.execute(
            old.tables["card_versions"]
            .insert()
            .values(
                id="existing-version",
                card_id="existing-card",
                number=1,
                payload={"name": "原场景"},
                content_hash="existing",
                published_at=now,
            )
        )
        db.execute(
            old.tables["completions"]
            .insert()
            .values(
                user_id="existing-user",
                card_id="existing-card",
                first_completed_at=now,
                last_completed_at=now,
                first_version_id="existing-version",
                last_version_id="existing-version",
                safe_name="原场景",
            )
        )
        before = {
            name: db.execute(select(table)).mappings().all()
            for name, table in old.tables.items()
            if name != "alembic_version"
        }
    command.upgrade(config, "0020")
    with engine.connect() as db:
        after = {name: db.execute(select(old.tables[name])).mappings().all() for name in before}
        assert before == after
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0020"
    assert (
        len([name for name in inspect(engine).get_table_names() if name.startswith("listening_")])
        == 13
    )
    command.upgrade(config, "0021")
    columns = {c["name"]: c for c in inspect(engine).get_columns("listening_articles")}
    assert columns["draft_topic_id"]["nullable"] and columns["draft_topic_order"]["nullable"]
    with engine.connect() as db:
        assert {
            name: db.execute(select(old.tables[name])).mappings().all() for name in before
        } == before
    command.upgrade(config, "0022")
    assert "name_en" in {c["name"] for c in inspect(engine).get_columns("listening_categories")}
    assert "description" in {c["name"] for c in inspect(engine).get_columns("listening_topics")}
    command.check(config)
    engine.dispose()


def test_listening_mysql_offline_ddl_is_pure_additive_and_microsecond(monkeypatch):
    monkeypatch.setenv("JUYA_DATABASE_URL", "mysql+pymysql://fixture:fixture@invalid/fixture")
    monkeypatch.delenv("JUYA_MIGRATION_DATABASE_URL", raising=False)
    config = Config("alembic.ini")
    output = StringIO()
    config.output_buffer = output
    command.upgrade(config, "0019:0020", sql=True)
    ddl = output.getvalue()
    assert ddl.count("CREATE TABLE listening_") == 13
    assert "DATETIME(6)" in ddl
    assert "DROP TABLE" not in ddl and "ALTER TABLE" not in ddl
    assert "UPDATE users" not in ddl and "UPDATE cards" not in ddl
    assert "FOREIGN KEY(user_id) REFERENCES users (id)" in ddl
    assert "CREATE INDEX ix_listening_jobs_state" in ddl
