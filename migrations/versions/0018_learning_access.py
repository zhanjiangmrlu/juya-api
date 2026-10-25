"""Add opt-in learning access without changing any account or learning fact."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import DATETIME

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "learning_free_policy",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("free_count", sa.Integer(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "learning_authorizations",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("starts_on", sa.Date()),
        sa.Column("expires_on", sa.Date()),
        sa.Column("revoked_at", sa.DateTime().with_variant(DATETIME(fsp=6), "mysql")),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_learning_authorizations_expires_on", "learning_authorizations", ["expires_on"]
    )
    op.create_table(
        "learning_access_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("admin_id", sa.String(36), sa.ForeignKey("administrators.id"), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("before", sa.JSON(), nullable=False),
        sa.Column("after", sa.JSON(), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime().with_variant(DATETIME(fsp=6), "mysql"), nullable=False
        ),
    )
    op.create_index("ix_learning_access_history_user_id", "learning_access_history", ["user_id"])


def downgrade():
    op.drop_table("learning_access_history")
    op.drop_table("learning_authorizations")
    op.drop_table("learning_free_policy")
