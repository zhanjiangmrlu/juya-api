"""Add independent optional PDF publications without changing learning identities."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import DATETIME

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade():
    """Nullable expansion keeps legacy records and contract-3 writers compatible."""
    bind = op.get_bind()
    if "current_study_note_version_id" not in {
        c["name"] for c in sa.inspect(bind).get_columns("cards")
    }:
        op.add_column(
            "cards",
            sa.Column(
                "current_study_note_version_id",
                sa.String(36),
                nullable=True,
                comment="当前已发布学习笔记独立版本标识；空表示无笔记",
            ),
        )
    if "ix_cards_current_study_note_version_id" not in {
        i["name"] for i in sa.inspect(bind).get_indexes("cards")
    }:
        op.create_index(
            "ix_cards_current_study_note_version_id", "cards", ["current_study_note_version_id"]
        )
    if "study_note" not in {c["name"] for c in sa.inspect(bind).get_columns("card_drafts")}:
        op.add_column(
            "card_drafts",
            sa.Column(
                "study_note",
                sa.JSON(),
                nullable=True,
                comment="学习笔记草稿决策JSON：keep保留、set设置、remove移除、unresolved待选择及有效与待处理媒体引用",
            ),
        )
    if "study_note" not in {c["name"] for c in sa.inspect(bind).get_columns("import_items")}:
        op.add_column(
            "import_items",
            sa.Column(
                "study_note",
                sa.JSON(),
                nullable=True,
                comment="学习笔记核对决策JSON，保留同包同目录候选、有效及待处理媒体引用",
            ),
        )
    if not sa.inspect(bind).has_table("card_study_note_versions"):
        op.create_table(
            "card_study_note_versions",
            sa.Column("id", sa.String(36), primary_key=True, comment="学习笔记版本内部标识"),
            sa.Column(
                "card_id",
                sa.String(36),
                sa.ForeignKey("cards.id"),
                nullable=False,
                comment="所属场景稳定标识，关联cards.id",
            ),
            sa.Column(
                "number",
                sa.Integer(),
                nullable=False,
                comment="同一场景内独立递增的笔记发布版本序号",
            ),
            sa.Column(
                "media_id",
                sa.String(36),
                sa.ForeignKey("media.id"),
                nullable=True,
                comment="有效PDF媒体标识；空表示已发布移除笔记",
            ),
            sa.Column(
                "filename",
                sa.String(512),
                nullable=True,
                comment="发布时PDF原文件名快照；移除时为空",
            ),
            sa.Column(
                "size", sa.Integer(), nullable=True, comment="发布时PDF实际字节数；移除时为空"
            ),
            sa.Column(
                "published_at",
                sa.DateTime().with_variant(DATETIME(fsp=6), "mysql"),
                nullable=False,
                comment="笔记版本发布时间（UTC，微秒精度）",
            ),
            sa.UniqueConstraint("card_id", "number", name="uq_card_study_note_version"),
            comment="场景学习笔记独立不可变发布版本，不改变正文学习身份",
        )
    if "ix_card_study_note_versions_card_id" not in {
        i["name"] for i in sa.inspect(bind).get_indexes("card_study_note_versions")
    }:
        op.create_index(
            "ix_card_study_note_versions_card_id", "card_study_note_versions", ["card_id"]
        )
    info = sa.inspect(bind)
    existing = {c["name"] for c in info.get_columns("media_tickets")}
    foreign = {tuple(f["constrained_columns"]) for f in info.get_foreign_keys("media_tickets")}
    if "study_note_version_id" not in existing or ("study_note_version_id",) not in foreign:
        with op.batch_alter_table("media_tickets") as batch:
            if "study_note_version_id" not in existing:
                batch.add_column(
                    sa.Column(
                        "study_note_version_id",
                        sa.String(36),
                        nullable=True,
                        comment="票据绑定的独立学习笔记版本；正文或摘要用途为空",
                    )
                )
            if ("study_note_version_id",) not in foreign:
                batch.create_foreign_key(
                    "fk_media_ticket_study_note_version",
                    "card_study_note_versions",
                    ["study_note_version_id"],
                    ["id"],
                )


def downgrade():
    """Do not silently discard PDF publication history or draft decisions."""
    raise RuntimeError("0026 stores study-note history; restore a verified pre-upgrade backup")
