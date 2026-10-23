"""Retain batch history while fencing deleted staging; older INSERT shapes remain valid."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import DATETIME

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "import_batches",
        sa.Column(
            "deleted_at", sa.DateTime().with_variant(DATETIME(fsp=6), "mysql"), nullable=True
        ),
    )


def downgrade():
    with op.batch_alter_table("import_batches") as batch:
        batch.drop_column("deleted_at")
