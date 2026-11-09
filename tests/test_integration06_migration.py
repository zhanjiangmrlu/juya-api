"""0024 preflight, deterministic ownership and preservation of old free sets."""

import os
from datetime import datetime

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData, Table, create_engine, inspect, select, text

from tests.test_import_recovery_migrations import migration_config


@pytest.fixture(params=["sqlite", pytest.param("mysql", marks=pytest.mark.mysql)])
def migration_database(tmp_path, monkeypatch, request):
    "Permit destructive migration fixtures only in an explicitly isolated local verification DB."
    url = (
        os.getenv("JUYA_TEST_DATABASE_URL")
        if request.param == "mysql"
        else "sqlite+pysqlite:///" + str(tmp_path / "upgrade.db")
    )
    if not url:
        pytest.skip("Dedicated MySQL verification database required")
    engine = create_engine(url, hide_parameters=True)
    if request.param == "mysql":
        if (
            engine.dialect.name != "mysql"
            or engine.url.database != "juya_verify"
            or engine.url.host not in {"127.0.0.1", "localhost", "::1"}
        ):
            raise RuntimeError("0024 migration requires the dedicated local juya_verify database")
        metadata = MetaData()
        metadata.reflect(engine)
        metadata.drop_all(engine)
    config = migration_config(monkeypatch, url)
    command.upgrade(config, "0023")
    yield config, engine
    engine.dispose()


def test_unknown_legacy_free_set_stops_before_any_schema_or_data_change(migration_database):
    """A scene ambiguity must also leave valid listening data and DDL untouched."""
    config, engine = migration_database
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO cards (id,status,current_version_id,sort_order,create"
                "d_at) VALUES ('unknown','published','v',1,'2026-10-01')"
            )
        )
        db.execute(
            text(
                "INSERT INTO listening_categories (id,name,sort_order,revision) "
                "VALUES ('cat','分类',0,1)"
            )
        )
    before = inspect(engine).get_table_names()
    with pytest.raises(RuntimeError, match="unknown"):
        command.upgrade(config, "head")
    assert inspect(engine).get_table_names() == before
    assert "category_id" not in {
        column["name"] for column in inspect(engine).get_columns("listening_articles")
    }
    with engine.connect() as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0023"
        assert db.scalar(text("SELECT name FROM listening_categories WHERE id='cat'")) == "分类"


def test_known_sets_and_category_order_are_frozen_without_rewriting_versions(migration_database):
    """Freeze the old effective list and flatten topics deterministically while keeping IDs."""
    config, engine = migration_database
    with engine.begin() as db:
        db.execute(text("INSERT INTO learning_free_policy VALUES (1,1,1,4)"))
        db.execute(text("INSERT INTO listening_policy VALUES (1,1,2,5)"))
        db.execute(
            text(
                "INSERT INTO listening_categories (id,name,sort_order,revision) "
                "VALUES ('cat','分类',0,1)"
            )
        )
        db.execute(
            text(
                "INSERT INTO listening_topics "
                "(id,category_id,name,sort_order,revision) VALUES "
                "('t','cat','旧主题',0,1)"
            )
        )
        for index in [1, 2]:
            db.execute(
                text(
                    "INSERT INTO cards (id,status,current_version_id,sort_order,create"
                    "d_at) VALUES (:id,'published','v',:n,'2026-10-01')"
                ),
                {"id": f"c{index}", "n": index},
            )
            db.execute(
                text(
                    "INSERT INTO listening_articles "
                    "(id,topic_id,status,revision,version_id,payload,topic_order,globa"
                    "l_order,source_hash,created_at) VALUES "
                    "(:id,'t','published',3,:version,'{}',:n,:n,'old-source','2026-10-"
                    "01')"
                ),
                {"id": f"a{index}", "version": f"v{index}", "n": index},
            )
    command.upgrade(config, "head")
    with engine.connect() as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == (
            ScriptDirectory.from_config(config).get_current_head()
        )
    command.upgrade(config, "head")
    with engine.connect() as db:
        assert db.execute(text("SELECT id,is_free,free_revision FROM cards ORDER BY id")).all() == [
            ("c1", 1, 1),
            ("c2", 0, 1),
        ]
        assert db.execute(
            text(
                "SELECT id,category_id,category_order,is_free,version_id,source_ha"
                "sh FROM listening_articles ORDER BY id"
            )
        ).all() == [
            ("a1", "cat", 1, 1, "v1", "old-source"),
            ("a2", "cat", 2, 0, "v2", "old-source"),
        ]
    with engine.connect() as db:
        assert (
            db.scalar(text("SELECT value FROM setting_counters WHERE name='schema_contract'")) == 3
        )
    assert inspect(engine).get_columns("listening_articles")[1]["nullable"]
    command.check(config)


def test_interrupted_ddl_resumes_from_durable_snapshot_without_reapplying_batch_revision(
    migration_database, monkeypatch
):
    """MySQL's partial DDL retains source facts and a retry applies each batch bump once."""
    from alembic.operations import Operations

    config, engine = migration_database
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO administrators(id,username,password_hash) VALUES "
                "('admin','admin','test')"
            )
        )
        db.execute(
            text(
                "INSERT INTO listening_categories(id,name,sort_order,revision) "
                "VALUES ('cat','分类',0,1)"
            )
        )
        db.execute(
            text(
                "INSERT INTO listening_topics(id,category_id,name,sort_order,revis"
                "ion) VALUES ('topic','cat','主题',0,1)"
            )
        )
        db.execute(
            text(
                "INSERT INTO listening_imports(id,admin_id,mode,status,revision,pa"
                "ckages,created_at) VALUES "
                "('batch','admin','zip','review',6,'[]','2026-10-01')"
            )
        )
        db.execute(
            text(
                "INSERT INTO listening_candidates(id,batch_id,package_id,path,stat"
                "e,payload,topic_id,source_hash,errors,resources,removed) VALUES "
                "('candidate','batch','package','file.docx','incomplete','{}','top"
                "ic','legacy-source','[]',:resources,0)"
            ),
            {"resources": '{"_metadata":{"target_article_id":null,"target_revision":null}}'},
        )
    with engine.begin() as db:
        operations = Table("operations", MetaData(), autoload_with=engine)
        db.execute(
            operations.insert().values(
                scope="admin:admin",
                key_digest="successful-key",
                action="listening.import.save",
                fingerprint="original-fingerprint",
                result="original-encrypted-receipt",
                accepted_at=datetime(2026, 10, 1),
            )
        )
    original = Operations.add_column

    def interrupt(self, table_name, column, **kwargs):
        """Fail after initial expansion DDL, where MySQL has already committed its snapshot."""
        if table_name == "listening_categories":
            raise RuntimeError("simulated ddl interruption")
        return original(self, table_name, column, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Operations, "add_column", interrupt)
        with pytest.raises(RuntimeError, match="simulated ddl interruption"):
            command.upgrade(config, "0024")
    if engine.dialect.name == "mysql":
        with engine.connect() as db:
            assert (
                db.scalar(text("SELECT COUNT(*) FROM content_migration_snapshots WHERE id='0024'"))
                == 1
            )
            assert db.scalar(text("SELECT revision FROM listening_imports WHERE id='batch'")) == 6
    command.upgrade(config, "0024")
    with engine.begin() as db:
        assert db.execute(
            text("SELECT id,category_id,source_hash,topic_id FROM listening_candidates")
        ).one() == ("candidate", "cat", "legacy-source", "topic")
        assert db.scalar(text("SELECT revision FROM listening_imports WHERE id='batch'")) == 7
        assert db.scalar(
            text("SELECT canonical_hash FROM listening_candidates WHERE id='candidate'")
        )
        db.execute(text("UPDATE alembic_version SET version_num='0023'"))
    command.upgrade(config, "0024")
    with engine.connect() as db:
        assert db.scalar(text("SELECT revision FROM listening_imports WHERE id='batch'")) == 7
    with engine.connect() as db:
        receipts = Table("operations", MetaData(), autoload_with=engine)
        assert (
            db.scalar(select(receipts.c.result).where(receipts.c.key_digest == "successful-key"))
            == "original-encrypted-receipt"
        )
    command.upgrade(config, "head")
    command.check(config)


def test_draft_category_orders_flatten_all_target_topics_after_existing_articles(
    migration_database,
):
    """Historical topic-relative draft positions become unique category-relative pending slots."""
    config, engine = migration_database
    metadata = MetaData()
    metadata.reflect(engine)
    with engine.begin() as db:
        db.execute(
            metadata.tables["listening_categories"].insert(),
            [
                {"id": "origin", "name": "原类", "sort_order": 0, "revision": 1},
                {"id": "target", "name": "目标", "sort_order": 1, "revision": 1},
            ],
        )
        db.execute(
            metadata.tables["listening_topics"].insert(),
            [
                {
                    "id": "source",
                    "category_id": "origin",
                    "name": "原",
                    "sort_order": 0,
                    "revision": 1,
                },
                {
                    "id": "one",
                    "category_id": "target",
                    "name": "第一主题",
                    "sort_order": 0,
                    "revision": 1,
                },
                {
                    "id": "two",
                    "category_id": "target",
                    "name": "第二主题",
                    "sort_order": 1,
                    "revision": 1,
                },
            ],
        )
        db.execute(
            metadata.tables["listening_policy"]
            .insert()
            .values(id=1, free_count=0, revision=0, catalog_revision=0)
        )
        rows = []
        for identifier, topic, draft in [
            ("existing-one", "one", None),
            ("existing-two", "two", None),
            ("move-first", "source", "one"),
            ("move-second", "source", "two"),
        ]:
            rows.append(
                {
                    "id": identifier,
                    "topic_id": topic,
                    "draft_topic_id": draft,
                    "draft_topic_order": 2 if draft else None,
                    "status": "published",
                    "revision": 2,
                    "version_id": "version-" + identifier,
                    "payload": {},
                    "topic_order": 1,
                    "global_order": len(rows) + 1,
                    "created_at": datetime(2026, 10, 1),
                }
            )
        db.execute(metadata.tables["listening_articles"].insert(), rows)
    command.upgrade(config, "head")
    with engine.connect() as db:
        values = {
            row.id: row
            for row in db.execute(
                text(
                    "SELECT id,category_id,category_order,draft_category_id,"
                    "draft_category_order FROM listening_articles"
                )
            )
        }
        assert [values[name].category_order for name in ["existing-one", "existing-two"]] == [1, 2]
        assert [values[name].draft_category_order for name in ["move-first", "move-second"]] == [
            3,
            4,
        ]
