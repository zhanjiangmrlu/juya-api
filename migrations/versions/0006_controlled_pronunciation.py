"""Controlled pronunciation cache; user/profile data is excluded.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pronunciations",
        sa.Column("cache_key", sa.String(64), primary_key=True),
        sa.Column("spelling", sa.String(300), nullable=False),
        sa.Column("reading", sa.String(300), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id")),
        sa.Column("media_id", sa.String(36), sa.ForeignKey("media.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("pronunciations")
