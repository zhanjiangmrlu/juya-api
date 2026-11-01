"""Flatten listening ownership and freeze legacy free sets before retiring numeric policies."""

import hashlib
import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def reflected(bind, name):
    """Reflect only the current migration table instead of importing mutable runtime models."""
    return sa.Table(name, sa.MetaData(), autoload_with=bind)


def canonical_hash(payload, media):
    """Freeze v1 no-word identity and v2 ordered word semantics without random IDs."""
    normalized = dict(payload)
    for field in ["audio_id", "image_id"]:
        normalized[field] = media.get(payload.get(field))
    words = normalized.pop("vocabulary", [])
    if words:
        normalized["vocabulary"] = [
            {
                key: value
                for key, value in word.items()
                if key not in {"id", "source", "source_hint"}
            }
            | {
                **(
                    {"source_hint": word.get("source_hint", "")}
                    if not word.get("source") and word.get("source_hint")
                    else {}
                ),
                "source": {
                    key: value
                    for key, value in (word.get("source") or {}).items()
                    if key != "confirmed"
                },
            }
            for word in words
        ]
        normalized = {"canonical_version": 2, "payload": normalized}
    return hashlib.sha256(
        json.dumps(normalized, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def preflight(bind):
    """Collect every ambiguity before the first DDL or data write; never guess free sets."""
    rows = {
        name: [dict(row) for row in bind.execute(sa.select(reflected(bind, name))).mappings()]
        for name in [
            "cards",
            "learning_free_policy",
            "listening_articles",
            "listening_policy",
            "listening_categories",
            "listening_topics",
            "listening_candidates",
            "listening_imports",
            "media",
        ]
    }
    errors = []
    free = {}
    for kind, table, policy_table, version, order in [
        ("scene", "cards", "learning_free_policy", "current_version_id", "sort_order"),
        ("listening", "listening_articles", "listening_policy", "version_id", "global_order"),
    ]:
        published = sorted(
            [
                row
                for row in rows[table]
                if row["status"] == "published" and row[version] and row["deleted_at"] is None
            ],
            key=lambda row: (row[order], row["id"]),
        )
        policy = next((row for row in rows[policy_table] if row["id"] == 1), None)
        known = (
            policy
            and isinstance(policy["free_count"], int)
            and policy["free_count"] >= 0
            and (kind != "scene" or policy["enabled"])
        )
        if published and not known:
            errors.append(
                {
                    "type": kind + ".unknown_free_set",
                    "count": len(published),
                    "ids": [row["id"] for row in published],
                }
            )
        free[kind] = [row["id"] for row in published[: policy["free_count"]]] if known else []
    categories = {row["id"] for row in rows["listening_categories"]}
    topics = {row["id"]: row for row in rows["listening_topics"]}
    mappings = {}
    for row in rows["listening_articles"]:
        topic, draft = (
            topics.get(row["topic_id"]),
            topics.get(row["draft_topic_id"]) if row["draft_topic_id"] else None,
        )
        if (
            not topic
            or topic["category_id"] not in categories
            or (row["draft_topic_id"] and (not draft or draft["category_id"] not in categories))
        ):
            errors.append({"type": "listening.invalid_category", "id": row["id"]})
            continue
        mappings[row["id"]] = {
            "category_id": topic["category_id"],
            "draft_category_id": draft["category_id"]
            if draft and draft["category_id"] != topic["category_id"]
            else None,
            "draft_category_order": row["draft_topic_order"] if draft else None,
        }
    grouped = {}
    for row in rows["listening_articles"]:
        if row["id"] in mappings:
            owner = mappings[row["id"]]["category_id"]
            grouped.setdefault(owner, []).append(row)
    for articles in grouped.values():
        articles.sort(
            key=lambda row: (
                topics[row["topic_id"]]["sort_order"],
                row["topic_id"],
                row["topic_order"],
                row["id"],
            )
        )
        for index, row in enumerate(articles, 1):
            mappings[row["id"]]["category_order"] = index
    candidates = {}
    revisions = {}
    for row in rows["listening_candidates"]:
        topic = topics.get(row["topic_id"]) if row["topic_id"] else None
        if row["topic_id"] and (not topic or topic["category_id"] not in categories):
            errors.append({"type": "candidate.invalid_category", "id": row["id"]})
        candidates[row["id"]] = topic["category_id"] if topic else None
        if not row["article_id"] and not row["removed"]:
            batch = next(
                batch for batch in rows["listening_imports"] if batch["id"] == row["batch_id"]
            )
            revisions[batch["id"]] = batch["revision"] + 1
    if errors:
        raise RuntimeError(
            "integration06 preflight requires review: " + json.dumps(errors, ensure_ascii=False)
        )
    media = {row["id"]: row["sha256"] for row in rows["media"]}
    return {
        "free": free,
        "articles": mappings,
        "candidates": candidates,
        "batch_revisions": revisions,
        "article_hashes": {
            row["id"]: canonical_hash(row["payload"], media) for row in rows["listening_articles"]
        },
        "candidate_hashes": {
            row["id"]: canonical_hash(row["payload"], media) for row in rows["listening_candidates"]
        },
    }


def upgrade():
    """Persist a pre-DDL snapshot so a MySQL interrupted expansion can safely resume."""
    if op.get_context().as_sql:
        raise RuntimeError(
            "0024 requires online preflight and a local backup; offline blind migration is disabled"
        )
    bind = op.get_bind()
    names = sa.inspect(bind).get_table_names()
    if "content_migration_snapshots" in names:
        saved = reflected(bind, "content_migration_snapshots")
        snapshot = bind.execute(
            sa.select(saved.c.payload).where(saved.c.id == "0024")
        ).scalar_one_or_none()
    else:
        snapshot = None
    if snapshot is None:
        snapshot = preflight(bind)
        if "content_migration_snapshots" not in names:
            op.create_table(
                "content_migration_snapshots",
                sa.Column("id", sa.String(16), primary_key=True),
                sa.Column("payload", sa.JSON(), nullable=False),
            )
        snapshot_table = reflected(bind, "content_migration_snapshots")
        statement = snapshot_table.insert().values(id="0024", payload=snapshot)
        if bind.dialect.name == "mysql":
            # Alembic must own the commit boundary so its final revision stamp is also committed.
            with op.get_context().autocommit_block():
                bind.execute(statement)
        else:
            bind.execute(statement)
    date_type = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")
    definitions = {
        "cards": [
            sa.Column("is_free", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("free_revision", sa.Integer(), nullable=False, server_default="1"),
        ],
        "listening_categories": [sa.Column("deleted_at", date_type)],
        "listening_articles": [
            sa.Column("category_id", sa.String(36)),
            sa.Column("draft_category_id", sa.String(36)),
            sa.Column("category_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("draft_category_order", sa.Integer()),
            sa.Column("is_free", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("free_revision", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("canonical_hash", sa.String(64)),
        ],
        "listening_candidates": [
            sa.Column("category_id", sa.String(36)),
            sa.Column("canonical_hash", sa.String(64)),
        ],
    }
    for name, columns in definitions.items():
        existing = {column["name"] for column in sa.inspect(bind).get_columns(name)}
        for column in columns:
            if column.name not in existing:
                op.add_column(name, column)
    for name, kind in [("cards", "scene"), ("listening_articles", "listening")]:
        table = reflected(bind, name)
        bind.execute(table.update().values(is_free=False))
        if snapshot["free"][kind]:
            bind.execute(
                table.update().where(table.c.id.in_(snapshot["free"][kind])).values(is_free=True)
            )
    articles, candidates, batches = [
        reflected(bind, name)
        for name in ["listening_articles", "listening_candidates", "listening_imports"]
    ]
    for identifier, values in snapshot["articles"].items():
        bind.execute(
            articles.update()
            .where(articles.c.id == identifier)
            .values(**values, canonical_hash=snapshot["article_hashes"][identifier])
        )
    for identifier, owner in snapshot["candidates"].items():
        bind.execute(
            candidates.update()
            .where(candidates.c.id == identifier)
            .values(category_id=owner, canonical_hash=snapshot["candidate_hashes"][identifier])
        )
    for identifier, value in snapshot["batch_revisions"].items():
        bind.execute(batches.update().where(batches.c.id == identifier).values(revision=value))
    for name in ["listening_articles", "listening_candidates"]:
        info = sa.inspect(bind)
        foreign = {tuple(item["constrained_columns"]) for item in info.get_foreign_keys(name)}
        columns = {column["name"]: column for column in info.get_columns(name)}
        with op.batch_alter_table(name) as batch:
            for field in (
                ["category_id", "draft_category_id"]
                if name == "listening_articles"
                else ["category_id"]
            ):
                if (field,) not in foreign:
                    batch.create_foreign_key(
                        "fk_" + name + "_" + field, "listening_categories", [field], ["id"]
                    )
            if name == "listening_articles":
                if not columns["topic_id"]["nullable"]:
                    batch.alter_column("topic_id", existing_type=sa.String(36), nullable=True)
                if columns["category_id"]["nullable"]:
                    batch.alter_column("category_id", existing_type=sa.String(36), nullable=False)
    counters = reflected(bind, "setting_counters")
    bind.execute(counters.update().where(counters.c.name == "schema_contract").values(value=3))
    for name, field in [
        ("listening_categories", "deleted_at"),
        ("listening_articles", "category_id"),
        ("listening_articles", "canonical_hash"),
        ("listening_candidates", "canonical_hash"),
    ]:
        index = "ix_" + name + "_" + field
        if index not in {item["name"] for item in sa.inspect(bind).get_indexes(name)}:
            op.create_index(index, name, [field])


def downgrade():
    """Reject a lossy downgrade once direct ownership and explicit flags can be edited."""
    raise RuntimeError("0024 cannot be downgraded without restoring a verified pre-upgrade backup")
