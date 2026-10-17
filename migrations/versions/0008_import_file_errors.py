"""Preserve individual archive member failures without rejecting readable sibling cards."""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("import_files", sa.Column("error_code", sa.String(64), nullable=True))


def downgrade():
    op.drop_column("import_files", "error_code")
