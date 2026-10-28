"""Add optional design taxonomy labels, preserving older INSERT and update requests."""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "listening_categories",
        sa.Column("name_en", sa.String(300), nullable=False, server_default=""),
    )
    op.add_column(
        "listening_topics",
        sa.Column("description", sa.String(2000), nullable=False, server_default=""),
    )


def downgrade():
    op.drop_column("listening_topics", "description")
    op.drop_column("listening_categories", "name_en")
