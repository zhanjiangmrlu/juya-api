"""Add an optional topic English label without rewriting existing business content."""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "listening_topics",
        sa.Column("name_en", sa.String(300), nullable=False, server_default=""),
    )


def downgrade():
    op.drop_column("listening_topics", "name_en")
