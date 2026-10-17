"""Persist actual archive parsing progress for recoverable multiple-ZIP imports."""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("import_files", sa.Column("progress", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("import_files", "progress")
