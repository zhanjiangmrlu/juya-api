"""Add administration-only receipts and source names without changing learner models."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import DATETIME

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "admin_action_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("admin_id", sa.String(36), sa.ForeignKey("administrators.id"), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime().with_variant(DATETIME(fsp=6), "mysql"), nullable=False
        ),
    )
    op.create_index("ix_admin_action_batches_admin_id", "admin_action_batches", ["admin_id"])
    op.create_table(
        "admin_action_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "batch_id", sa.String(36), sa.ForeignKey("admin_action_batches.id"), nullable=False
        ),
        sa.Column("card_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("version_id", sa.String(36)),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id")),
        sa.Column("skip_reason", sa.String(64)),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("batch_id", "card_id", name="uq_admin_action_card"),
    )
    op.create_index("ix_admin_action_items_batch_id", "admin_action_items", ["batch_id"])
    op.create_table(
        "admin_media_sources",
        sa.Column("media_id", sa.String(36), sa.ForeignKey("media.id"), primary_key=True),
        sa.Column("original_name", sa.String(255), nullable=False),
    )


def downgrade():
    op.drop_table("admin_media_sources")
    op.drop_table("admin_action_items")
    op.drop_table("admin_action_batches")
