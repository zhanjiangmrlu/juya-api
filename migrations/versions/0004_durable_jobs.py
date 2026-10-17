"""Durable jobs with database dispatch recovery and worker leases.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("owner_kind", sa.String(16), nullable=False),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("dispatch_after", sa.DateTime(), nullable=False),
        sa.Column("lease", sa.String(36)),
        sa.Column("lease_expires_at", sa.DateTime()),
        sa.Column("error_code", sa.String(64)),
        sa.Column("result", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for column in ["owner_id", "state", "available_at", "dispatch_after"]:
        op.create_index("ix_jobs_" + column, "jobs", [column])

    op.add_column("media", sa.Column("job_id", sa.String(36), nullable=True))
    op.create_index("ix_media_job_id", "media", ["job_id"])


def downgrade():
    op.drop_index("ix_media_job_id", "media")
    op.drop_column("media", "job_id")
    op.drop_table("jobs")
