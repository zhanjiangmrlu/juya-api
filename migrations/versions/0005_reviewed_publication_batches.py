"""Reviewed publication batches with durable per-card results.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "publication_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("admin_id", sa.String(36), sa.ForeignKey("administrators.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_publication_batches_admin_id", "publication_batches", ["admin_id"])
    op.create_table(
        "publication_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "batch_id", sa.String(36), sa.ForeignKey("publication_batches.id"), nullable=False
        ),
        sa.Column("card_id", sa.String(36), sa.ForeignKey("cards.id"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("preview_id", sa.String(36), nullable=False),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("batch_id", "card_id", name="uq_publication_batch_card"),
    )
    op.create_index("ix_publication_items_batch_id", "publication_items", ["batch_id"])


def downgrade():
    op.drop_table("publication_items")
    op.drop_table("publication_batches")
