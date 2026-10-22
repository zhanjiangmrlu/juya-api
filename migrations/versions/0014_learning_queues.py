"""新增阅读开始及本人来源队列，不改变完成和打卡历史"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import DATETIME

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    """添加独立导航状态与稳定ID顺序表，已有业务行保持原值"""
    op.create_table(
        "reading_starts",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("card_id", sa.String(36), sa.ForeignKey("cards.id"), primary_key=True),
        sa.Column(
            "started_at", sa.DateTime().with_variant(DATETIME(fsp=6), "mysql"), nullable=False
        ),
        sa.Column("position", sa.JSON(), nullable=True),
    )
    op.create_table(
        "learning_queues",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("day", sa.Date(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime().with_variant(DATETIME(fsp=6), "mysql"), nullable=False
        ),
        sa.Column(
            "expires_at", sa.DateTime().with_variant(DATETIME(fsp=6), "mysql"), nullable=False
        ),
    )
    op.create_index("ix_learning_queues_user_id", "learning_queues", ["user_id"])
    op.create_index("ix_learning_queues_expires_at", "learning_queues", ["expires_at"])
    op.create_table(
        "learning_queue_items",
        sa.Column("queue_id", sa.String(36), sa.ForeignKey("learning_queues.id"), primary_key=True),
        sa.Column("position", sa.Integer(), primary_key=True),
        sa.Column("card_id", sa.String(36), sa.ForeignKey("cards.id"), nullable=False),
    )


def downgrade():
    """仅回退本轮导航表，保留完成、收藏及打卡数据"""
    op.drop_table("learning_queue_items")
    op.drop_index("ix_learning_queues_expires_at", table_name="learning_queues")
    op.drop_index("ix_learning_queues_user_id", table_name="learning_queues")
    op.drop_table("learning_queues")
    op.drop_table("reading_starts")
