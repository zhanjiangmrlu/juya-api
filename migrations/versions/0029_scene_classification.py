"""Add nullable classification and import review fields without assigning historical cards."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import DATETIME

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    def add(table, column):
        if column.name not in {c["name"] for c in sa.inspect(bind).get_columns(table)}:
            op.add_column(table, column)

    add(
        "import_batches",
        sa.Column(
            "removed_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="人工移除的候选卡片累计数量",
        ),
    )
    types = [
        ("cards", "published_content_type", "当前发布分类投影", "ck_card_published_type"),
        ("card_drafts", "content_type", "草稿拟发布分类，空值待核对", "ck_card_draft_type"),
        ("learning_queues", "content_type", "待学来源分类快照", "ck_queue_type"),
        ("import_items", "content_type", "候选拟发布分类", "ck_import_item_type"),
    ]
    for table, name, comment, check in types:
        add(
            table,
            sa.Column(
                name,
                sa.String(16),
                sa.CheckConstraint(f"{name} IN ('illustrated','intensive')", name=check),
                comment=comment,
            ),
        )
    add(
        "cards",
        sa.Column(
            "current_content_type_version_id", sa.String(36), comment="当前不可变分类版本标识"
        ),
    )
    if "ix_card_type_listing" not in {i["name"] for i in sa.inspect(bind).get_indexes("cards")}:
        op.create_index(
            "ix_card_type_listing", "cards", ["published_content_type", "status", "deleted_at"]
        )
    add("import_items", sa.Column("type_origin", sa.String(16), comment="分类值来源"))
    add("import_items", sa.Column("type_raw", sa.JSON(), comment="文件中原始分类文字"))
    for table in ("import_items", "listening_candidates"):
        add(table, sa.Column("duplicate_detail", sa.JSON(), comment="重复判定及来源快照"))
    if sa.inspect(bind).has_table("card_content_type_versions"):
        return
    op.create_table(
        "card_content_type_versions",
        sa.Column("id", sa.String(36), primary_key=True, comment="分类版本标识"),
        sa.Column(
            "card_id", sa.String(36), sa.ForeignKey("cards.id"), nullable=False, comment="所属场景"
        ),
        sa.Column("number", sa.Integer(), nullable=False, comment="本卡分类版本序号"),
        sa.Column("content_type", sa.String(16), nullable=False, comment="有效发布分类"),
        sa.Column(
            "version_id",
            sa.String(36),
            sa.ForeignKey("card_versions.id"),
            nullable=False,
            comment="发布正文版本",
        ),
        sa.Column(
            "study_note_version_id",
            sa.String(36),
            sa.ForeignKey("card_study_note_versions.id"),
            comment="发布笔记版本，含明确移除版本",
        ),
        sa.Column(
            "admin_id",
            sa.String(36),
            sa.ForeignKey("administrators.id"),
            nullable=False,
            comment="确认管理员",
        ),
        sa.Column(
            "created_at",
            sa.DateTime().with_variant(DATETIME(fsp=6), "mysql"),
            nullable=False,
            comment="确认时间UTC",
        ),
        sa.UniqueConstraint("card_id", "number", name="uq_card_type_version"),
        sa.CheckConstraint(
            "content_type IN ('illustrated','intensive')", name="ck_card_type_version"
        ),
        comment="场景发布分类与不可变正文、笔记绑定",
    )


def downgrade():
    raise RuntimeError("保留不可变分类与导入审核历史")
