"""Historical MySQL expansion keeps recorded activity and older image inserts compatible."""

import os
from datetime import datetime

import pytest
from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from sqlalchemy import MetaData, create_engine, inspect, select, text
from sqlalchemy.orm import Session


@pytest.mark.mysql
@pytest.mark.skipif(
    not os.getenv("JUYA_TEST_DATABASE_URL"), reason="Historical MySQL import migration verification"
)
def test_mysql_historical_import_upgrade_and_old_image_insert_survive_round_trip(
    tmp_path, monkeypatch
):
    # Register the complete metadata before clearing only the dedicated test schema.
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
    from juya_api.config import Settings
    from juya_api.content_models import Media
    from juya_api.database import Base
    from juya_api.import_models import ImportBatch, ImportFile, ImportItem
    from juya_api.import_service import batch_view
    from juya_api.job_models import Job
    from juya_api.models import Administrator

    url = os.environ["JUYA_TEST_DATABASE_URL"]
    engine = create_engine(url, hide_parameters=True)
    try:
        if engine.dialect.name != "mysql" or engine.url.database != "juya_verify":
            raise RuntimeError("Migration tests require the dedicated MySQL verification database")
        Base.metadata.drop_all(engine)
        with engine.begin() as db:
            db.execute(text("DROP TABLE IF EXISTS alembic_version"))
        monkeypatch.setenv("JUYA_DATABASE_URL", url)
        monkeypatch.delenv("JUYA_MIGRATION_DATABASE_URL", raising=False)
        config = Config("alembic.ini")
        command.upgrade(config, "0015")
        previous = MetaData()
        previous.reflect(engine)
        created = datetime(2026, 10, 17, 8, 0, 0, 123456)
        uploaded = datetime(2026, 10, 17, 8, 1, 0, 234567)
        moments = {
            "parse": datetime(2026, 10, 17, 8, 2, 0, 345678),
            "save": datetime(2026, 10, 17, 8, 3, 0, 456789),
            "media-original": datetime(2026, 10, 17, 8, 4, 0, 567890),
            "media-current": datetime(2026, 10, 17, 8, 5, 0, 678901),
            "unrelated": datetime(2026, 10, 18, 12, 0, 0, 999999),
        }
        mixed_time = datetime(2026, 10, 17, 8, 6, 0, 789012)
        batch_ids = ["empty", "uploaded", "parsed", "saved", "media", "mixed"]
        with Session(engine) as db, db.begin():
            db.add(Administrator(id="admin", username="migration-admin", password_hash="fixture"))
            db.flush()
            db.execute(
                previous.tables["import_batches"].insert(),
                [
                    {"id": name, "admin_id": "admin", "mode": "docx", "created_at": created}
                    for name in batch_ids
                ],
            )
            for name, moment in moments.items():
                db.add(
                    Job(
                        id=name,
                        kind="import.save"
                        if name == "save"
                        else "media.decode"
                        if name.startswith("media-")
                        else "import.parse",
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
                    id="medium",
                    owner_kind="admin",
                    owner_id="admin",
                    kind="audio",
                    state="ready",
                    storage_key="migration/source-audio",
                    content_type="audio/mpeg",
                    size=1,
                    sha256="fixture",
                    job_id="media-current",
                    created_at=created,
                )
            )
            db.flush()
            for name in batch_ids[1:]:
                db.add(
                    ImportFile(
                        id="file-" + name,
                        batch_id=name,
                        name=name + ".docx",
                        kind="docx",
                        storage_key="migration/" + name,
                        size=1,
                        sha256=name,
                        job_id={"parsed": "parse", "media": "media-original", "mixed": "parse"}.get(
                            name
                        ),
                        media_id="medium" if name in {"media", "mixed"} else None,
                        created_at=mixed_time if name == "mixed" else uploaded,
                    )
                )
            db.flush()
            for name in ["saved", "mixed"]:
                db.add(
                    ImportItem(
                        id="item-" + name,
                        batch_id=name,
                        source_file_id="file-" + name,
                        source_index=0,
                        source_identity=name,
                        content={"name": "retained synthetic staging"},
                        position=0,
                        job_id="save",
                    )
                )

        def facts():
            with engine.connect() as db:
                return {
                    name: db.execute(select(table).order_by(*table.primary_key.columns)).all()
                    for name in [
                        "administrators",
                        "jobs",
                        "media",
                        "import_batches",
                        "import_files",
                        "import_items",
                    ]
                    for table in [previous.tables[name]]
                }

        original = facts()
        command.upgrade(config, "head")
        assert facts() == original
        column = next(
            column
            for column in inspect(engine).get_columns("import_batches")
            if column["name"] == "updated_at"
        )
        assert column["nullable"] and column["default"] is None
        expected = {
            "empty": created,
            "uploaded": uploaded,
            "parsed": moments["parse"],
            "saved": moments["save"],
            "media": moments["media-current"],
            "mixed": mixed_time,
        }
        with Session(engine) as db, db.begin():
            assert (
                dict(db.execute(select(ImportBatch.id, ImportBatch.updated_at)).all()) == expected
            )
            # This reflected 0015 table emits the exact old column set, omitting updated_at.
            db.execute(
                previous.tables["import_batches"].insert(),
                {"id": "old-image", "admin_id": "admin", "mode": "docx", "created_at": created},
            )
            batch = db.get(ImportBatch, "old-image")
            assert batch.updated_at is None
            value = batch_view(
                db,
                batch,
                Settings(
                    environment="test",
                    database_url=url,
                    media_root=tmp_path / "media",
                    field_encryption_key=Fernet.generate_key().decode(),
                    lookup_key="synthetic-migration-lookup-key-only",
                ),
            )
            assert value["updated_at"] == "2026-10-17T08:00:00.123456Z"
        command.check(config)
        before_round_trip = facts()
        command.downgrade(config, "0015")
        assert "updated_at" not in {
            column["name"] for column in inspect(engine).get_columns("import_batches")
        }
        assert facts() == before_round_trip
        command.upgrade(config, "head")
        assert facts() == before_round_trip
        with Session(engine) as db:
            assert dict(db.execute(select(ImportBatch.id, ImportBatch.updated_at)).all()) == {
                **expected,
                "old-image": created,
            }
        command.check(config)
    finally:
        engine.dispose()
