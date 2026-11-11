"""Add durable cross-page free batches; never rewrite existing business tables."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import DATETIME

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade():
    """Create only two additive tables, preserving all old columns and historical rows."""
    bind = op.get_bind()
    instant = sa.DateTime().with_variant(DATETIME(fsp=6), "mysql")
    if not sa.inspect(bind).has_table("free_access_batches"):
        op.create_table(
            "free_access_batches",
            sa.Column("id", sa.String(36), primary_key=True, comment="批次标识"),
            sa.Column(
                "admin_id",
                sa.String(36),
                sa.ForeignKey("administrators.id"),
                nullable=False,
                comment="操作管理员",
            ),
            sa.Column(
                "job_id",
                sa.String(36),
                sa.ForeignKey("jobs.id"),
                nullable=False,
                unique=True,
                comment="持久任务标识",
            ),
            sa.Column(
                "parent_id",
                sa.String(36),
                sa.ForeignKey("free_access_batches.id"),
                comment="失败重试的原批次",
            ),
            sa.Column(
                "content_type", sa.String(16), nullable=False, comment="内容类型scene或listening"
            ),
            sa.Column("is_free", sa.Boolean(), nullable=False, comment="目标免费状态"),
            sa.Column("created_at", instant, nullable=False, comment="接受时间UTC"),
            comment="跨页免费设置任务及冻结选择",
        )
    if not sa.inspect(bind).has_table("free_access_batch_items"):
        op.create_table(
            "free_access_batch_items",
            sa.Column(
                "batch_id",
                sa.String(36),
                sa.ForeignKey("free_access_batches.id"),
                primary_key=True,
                comment="所属批次",
            ),
            sa.Column("content_id", sa.String(36), primary_key=True, comment="稳定内容标识"),
            sa.Column("position", sa.Integer(), nullable=False, comment="原选择顺序"),
            sa.Column(
                "snapshot", sa.JSON(), nullable=False, comment="确认前已展示的发布及免费版本快照"
            ),
            sa.Column(
                "status",
                sa.String(16),
                nullable=False,
                comment="逐项状态：pending待处理、succeeded成功、skipped跳过、failed失败",
            ),
            sa.Column("reason", sa.String(64), comment="跳过或失败原因码"),
            sa.Column("message", sa.String(300), comment="完整原因说明"),
            sa.Column("completed_at", instant, comment="逐项完成时间UTC"),
            comment="完整选择名单、预览快照及逐项执行回执",
        )


def downgrade():
    """Retain all immutable batches and audits during compatible contract-3 rollback."""
    raise RuntimeError("Free batch history must not be destructively removed")
