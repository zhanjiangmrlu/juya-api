"""Import recovery migration preserves facts and derives only recorded activity times."""

from datetime import UTC, datetime, timedelta
from io import StringIO

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, create_engine, inspect, select, text
from sqlalchemy.orm import Session


def migration_config(monkeypatch, url):
    monkeypatch.setenv("JUYA_DATABASE_URL", url)
    monkeypatch.delenv("JUYA_MIGRATION_DATABASE_URL", raising=False)
    return Config("alembic.ini")


def test_old_image_insert_after_upgrade_has_real_time_fallback_and_accepts_new_writes(
    tmp_path, monkeypatch
):
    from fastapi.testclient import TestClient

    from juya_api.admin import create_app
    from juya_api.auth import create_administrator
    from juya_api.config import Settings
    from juya_api.database import make_database
    from juya_api.import_models import ImportBatch

    from .content_helpers import key, picture

    url = "sqlite+pysqlite:///" + str(tmp_path / "old-image-import.db")
    config = migration_config(monkeypatch, url)
    command.upgrade(config, "0015")
    settings = Settings(
        environment="test",
        database_url=url,
        media_root=tmp_path / "media",
        field_encryption_key="yK1Xc0sWCxUQxXvHPEgY46iVE1mW6BwJqHWSeg1oEJ4=",
        lookup_key="test-lookup-secret-with-at-least-32-characters",
    )
    engine, sessions = make_database(settings)
    created = datetime(2026, 10, 17, 8, 0, 0, 123456)
    now = [created.replace(tzinfo=UTC) + timedelta(hours=1)]
    try:
        with sessions.begin() as db:
            admin = create_administrator(db, "admin", "correct-test-password")
            admin_id = admin.id
        command.upgrade(config, "0016")
        with sessions.begin() as db:
            # The previous image's mapped INSERT omits the new column after expansion.
            db.execute(
                text(
                    "INSERT INTO import_batches (id, admin_id, mode, created_at) "
                    "VALUES (:id, :admin_id, 'docx', :created_at)"
                ),
                {
                    "id": "old-image-batch",
                    "admin_id": admin_id,
                    "created_at": created.isoformat(" ", timespec="microseconds"),
                },
            )
            assert db.get(ImportBatch, "old-image-batch").updated_at is None
        with TestClient(
            create_app(settings, sessions=sessions, clock=lambda: now[0]),
            base_url="https://testserver",
        ) as client:
            login = client.post(
                "/api/admin/v1/auth/login",
                json={"username": "admin", "password": "correct-test-password"},
            )
            assert login.status_code == 200, login.text
            client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
            restored = client.get("/api/admin/v1/imports/old-image-batch")
            assert restored.status_code == 200, restored.text
            assert restored.json()["updated_at"] == "2026-10-17T08:00:00.123456Z"
            uploaded = client.post(
                "/api/admin/v1/imports/old-image-batch/files?kind=image",
                headers=key(),
                files={"file": ("new-write.png", picture(), "image/png")},
            )
            assert uploaded.status_code == 201, uploaded.text
            current = client.get("/api/admin/v1/imports/old-image-batch").json()
            assert current["updated_at"] == "2026-10-17T09:00:00.123456Z"
        with sessions() as db:
            assert db.get(ImportBatch, "old-image-batch").updated_at == now[0].replace(tzinfo=None)
        command.check(config)
    finally:
        engine.dispose()


def test_fresh_import_timestamp_is_nullable_and_matches_runtime_metadata(tmp_path, monkeypatch):
    url = "sqlite+pysqlite:///" + str(tmp_path / "fresh-import.db")
    config = migration_config(monkeypatch, url)
    command.upgrade(config, "head")
    engine = create_engine(url)
    try:
        columns = {
            column["name"]: column for column in inspect(engine).get_columns("import_batches")
        }
        assert "updated_at" in columns
        assert columns["updated_at"]["nullable"] is True
        assert columns["updated_at"]["default"] is None
        with engine.begin() as db:
            assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0016"
            assert db.scalar(text("SELECT count(*) FROM import_batches")) == 0
            db.execute(
                text(
                    "INSERT INTO administrators (id, username, password_hash) "
                    "VALUES ('admin', 'fixture-admin', 'fixture-only')"
                )
            )
        with engine.begin() as db:
            db.execute(
                text(
                    "INSERT INTO import_batches (id, admin_id, mode, created_at, updated_at) "
                    "VALUES ('missing-time', 'admin', 'multiple', '2026-10-17 08:00:00', NULL)"
                )
            )
        command.check(config)
    finally:
        engine.dispose()


def test_import_timestamp_upgrade_retains_business_and_backfills_recorded_activity(
    tmp_path, monkeypatch
):
    from juya_api.content_models import Card, CardVersion, Media
    from juya_api.import_models import ImportFile, ImportItem
    from juya_api.job_models import Job
    from juya_api.learning_models import Completion
    from juya_api.models import Administrator, User

    url = "sqlite+pysqlite:///" + str(tmp_path / "existing-import.db")
    config = migration_config(monkeypatch, url)
    command.upgrade(config, "0015")
    engine = create_engine(url)
    created = datetime(2026, 10, 17, 8, 0, 0, 123456)
    batch_ids = [
        "empty",
        "uploaded",
        "parsed",
        "saved",
        "media-file",
        "media-current",
        "older",
        "mixed",
    ]
    metadata = MetaData()
    metadata.reflect(engine)
    with Session(engine) as db, db.begin():
        db.add(Administrator(id="admin", username="fixture-admin", password_hash="fixture-only"))
        db.add(
            User(
                id="user",
                app_id="fixture",
                openid_digest="user",
                registered_at=created,
                last_login_at=created,
            )
        )
        db.add(
            Card(id="card", status="published", current_version_id="version", created_at=created)
        )
        db.flush()
        db.add(
            CardVersion(
                id="version",
                card_id="card",
                number=1,
                payload={"name": "retained"},
                content_hash="fixture",
                published_at=created,
            )
        )
        db.flush()
        db.add(
            Completion(
                user_id="user",
                card_id="card",
                first_completed_at=created,
                last_completed_at=created,
                first_version_id="version",
                last_version_id="version",
                safe_name="retained",
            )
        )
        db.execute(
            metadata.tables["import_batches"].insert(),
            [
                {"id": batch_id, "admin_id": "admin", "mode": "multiple", "created_at": created}
                for batch_id in batch_ids
            ],
        )
        for job_id, kind, moment in [
            ("parse", "import.parse", datetime(2026, 10, 17, 8, 2, 0, 345678)),
            ("save", "import.save", datetime(2026, 10, 17, 8, 3, 0, 456789)),
            ("media-original", "media.decode", datetime(2026, 10, 17, 8, 4, 0, 567890)),
            ("media-retry", "media.decode", datetime(2026, 10, 17, 8, 5, 0, 678901)),
            ("unrelated", "import.parse", datetime(2026, 10, 18, 12)),
        ]:
            db.add(
                Job(
                    id=job_id,
                    kind=kind,
                    owner_kind="admin",
                    owner_id="admin",
                    payload="{}",
                    state="succeeded",
                    available_at=created,
                    dispatch_after=created,
                    created_at=created,
                    updated_at=moment,
                )
            )
        db.flush()
        db.add(
            Media(
                id="media",
                owner_kind="admin",
                owner_id="admin",
                kind="audio",
                state="ready",
                job_id="media-retry",
                storage_key="fixture/media",
                size=1,
                content_type="audio/mpeg",
                sha256="fixture-media",
                created_at=created,
            )
        )
        db.flush()
        for batch_id in batch_ids[1:]:
            moment = (
                datetime(2026, 10, 17, 7, 59)
                if batch_id == "older"
                else datetime(2026, 10, 17, 8, 6, 0, 789012)
                if batch_id == "mixed"
                else datetime(2026, 10, 17, 8, 1, 0, 234567)
            )
            db.add(
                ImportFile(
                    id="file-" + batch_id,
                    batch_id=batch_id,
                    parent_id="",
                    name=batch_id + ".docx",
                    kind="docx",
                    storage_key="fixture/" + batch_id,
                    size=1,
                    sha256=batch_id,
                    job_id={
                        "parsed": "parse",
                        "media-file": "media-original",
                        "mixed": "parse",
                    }.get(batch_id),
                    media_id="media" if batch_id in {"media-current", "mixed"} else None,
                    created_at=moment,
                )
            )
        db.flush()
        db.add(
            ImportItem(
                id="item-saved",
                batch_id="saved",
                source_file_id="file-saved",
                source_index=0,
                source_identity="fixture",
                content={"name": "retained"},
                position=0,
                saved_card_id="card",
                saved_draft_revision=1,
                last_saved_hash="fixture",
                job_id="save",
            )
        )
        db.add(
            ImportItem(
                id="item-mixed",
                batch_id="mixed",
                source_file_id="file-mixed",
                source_index=0,
                source_identity="mixed",
                content={"name": "mixed"},
                position=0,
                job_id="save",
            )
        )
    with engine.connect() as connection:
        before = {
            table.name: list(connection.execute(select(table)).mappings())
            for table in metadata.sorted_tables
            if table.name not in {"alembic_version", "import_batches"}
        }
    command.upgrade(config, "head")
    columns = {column["name"]: column for column in inspect(engine).get_columns("import_batches")}
    assert "updated_at" in columns
    assert columns["updated_at"]["nullable"] is True
    metadata_after = MetaData()
    metadata_after.reflect(engine)
    with engine.connect() as connection:
        after = {
            table.name: list(connection.execute(select(table)).mappings())
            for table in metadata_after.sorted_tables
            if table.name not in {"alembic_version", "import_batches"}
        }
        assert after == before
        rows = {
            row["id"]: row
            for row in connection.execute(
                select(metadata_after.tables["import_batches"])
            ).mappings()
        }
        assert {key: row["updated_at"] for key, row in rows.items()} == {
            "empty": created,
            "uploaded": datetime(2026, 10, 17, 8, 1, 0, 234567),
            "parsed": datetime(2026, 10, 17, 8, 2, 0, 345678),
            "saved": datetime(2026, 10, 17, 8, 3, 0, 456789),
            "media-file": datetime(2026, 10, 17, 8, 4, 0, 567890),
            "media-current": datetime(2026, 10, 17, 8, 5, 0, 678901),
            "older": created,
            "mixed": datetime(2026, 10, 17, 8, 6, 0, 789012),
        }
        assert all(row["created_at"] == created for row in rows.values())
        assert all(
            row["mode"] == "multiple" and row["admin_id"] == "admin" for row in rows.values()
        )
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    command.check(config)
    command.downgrade(config, "0015")
    assert "updated_at" not in {c["name"] for c in inspect(engine).get_columns("import_batches")}
    command.upgrade(config, "head")
    command.check(config)
    engine.dispose()


def test_import_timestamp_migration_emits_mysql_microsecond_ddl_without_live_connection(
    monkeypatch,
):
    config = migration_config(monkeypatch, "mysql+pymysql://fixture:fixture@invalid/fixture")
    output = StringIO()
    config.output_buffer = output
    command.upgrade(config, "0015:head", sql=True)
    ddl = output.getvalue()
    assert "ADD COLUMN updated_at DATETIME(6)" in ddl
    assert "updated_at DATETIME(6) NOT NULL" not in ddl
    assert "UPDATE import_batches SET updated_at=import_batches.created_at" in ddl
    assert "CURRENT_TIMESTAMP" not in ddl.upper()
    assert "NOW()" not in ddl.upper()
