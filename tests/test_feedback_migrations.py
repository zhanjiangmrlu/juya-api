"""Additive feedback migration preserves existing learning facts and matches runtime metadata."""

from datetime import datetime

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session


def test_feedback_upgrade_and_downgrade_preserve_existing_learning(tmp_path, monkeypatch):
    url = "sqlite+pysqlite:///" + str(tmp_path / "migration-only.db")
    monkeypatch.setenv("JUYA_DATABASE_URL", url)
    monkeypatch.delenv("JUYA_MIGRATION_DATABASE_URL", raising=False)
    config = Config("alembic.ini")
    command.upgrade(config, "0014")
    from juya_api.content_models import Card, CardVersion
    from juya_api.learning_models import Checkin, Completion, DailyLearning
    from juya_api.models import User

    engine = create_engine(url)
    moment = datetime(2026, 10, 17, 8)
    with Session(engine) as db, db.begin():
        db.add(
            User(
                id="existing-user",
                app_id="fixture-app",
                openid_digest="existing-openid",
                registered_at=moment,
                last_login_at=moment,
            )
        )
        db.add(
            Card(
                id="existing-card",
                status="published",
                current_version_id="existing-version",
                created_at=moment,
            )
        )
        db.flush()
        db.add(
            CardVersion(
                id="existing-version",
                card_id="existing-card",
                number=1,
                payload={"name": "existing"},
                content_hash="fixture",
                published_at=moment,
            )
        )
        db.flush()
        db.add(
            Completion(
                user_id="existing-user",
                card_id="existing-card",
                first_completed_at=moment,
                last_completed_at=moment,
                first_version_id="existing-version",
                last_version_id="existing-version",
                safe_name="existing",
            )
        )
        db.add(
            DailyLearning(
                user_id="existing-user",
                card_id="existing-card",
                date=moment.date(),
                accepted_at=moment,
                version_id="existing-version",
            )
        )
        db.add(Checkin(user_id="existing-user", date=moment.date(), accepted_at=moment))
    command.upgrade(config, "0015")
    expected = {"feedbacks", "feedback_events", "feedback_reads", "feedback_images"}
    assert expected <= set(inspect(engine).get_table_names())
    assert "event_position" in {
        column["name"] for column in inspect(engine).get_columns("feedback_images")
    }
    command.upgrade(config, "head")
    command.check(config)
    for revision in ["0014", "0015"]:
        (command.downgrade if revision == "0014" else command.upgrade)(config, revision)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM users")) == 1
            assert connection.scalar(text("SELECT count(*) FROM completions")) == 1
            assert connection.scalar(text("SELECT count(*) FROM daily_learning")) == 1
            assert connection.scalar(text("SELECT count(*) FROM checkins")) == 1
            assert str(
                connection.scalar(text("SELECT first_completed_at FROM completions"))
            ).startswith("2026-10-17 08:00:00")
    command.upgrade(config, "head")
    command.check(config)
    engine.dispose()
