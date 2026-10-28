"""Isolate unpublished topic edits from the current published listening collection."""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("listening_articles") as batch:
        batch.add_column(sa.Column("draft_topic_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("draft_topic_order", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_listening_draft_topic", "listening_topics", ["draft_topic_id"], ["id"]
        )


def downgrade():
    with op.batch_alter_table("listening_articles") as batch:
        batch.drop_constraint("fk_listening_draft_topic", type_="foreignkey")
        batch.drop_column("draft_topic_order")
        batch.drop_column("draft_topic_id")
