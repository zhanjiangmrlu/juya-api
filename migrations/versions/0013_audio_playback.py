"""Link immutable originals to playback without changing existing publications."""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    for table in ["publication_items", "admin_action_items"]:
        op.add_column(
            table, sa.Column("title_en", sa.String(300), nullable=False, server_default="")
        )
    op.add_column("media", sa.Column("playback_id", sa.String(36), nullable=True))
    op.add_column("media", sa.Column("processing_stage", sa.String(24), nullable=True))


def downgrade():
    for table in ["publication_items", "admin_action_items"]:
        op.drop_column(table, "title_en")
    op.drop_column("media", "processing_stage")
    op.drop_column("media", "playback_id")
