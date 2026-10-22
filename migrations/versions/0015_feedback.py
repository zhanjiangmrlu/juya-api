"""Private feedback conversations, ordered events, read cursors and image attachments."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import DATETIME

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def instant():
    return sa.DateTime().with_variant(DATETIME(fsp=6), "mysql")


def upgrade():
    op.create_table(
        "feedbacks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("summary_cipher", sa.Text(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("card_id", sa.String(36), nullable=True),
        sa.Column("version_id", sa.String(36), nullable=True),
        sa.Column("source_title", sa.String(160), nullable=True),
        sa.Column("source_title_en", sa.String(300), nullable=False),
        sa.Column("latest_event_id", sa.Integer(), nullable=False),
        sa.Column("latest_user_event_id", sa.Integer(), nullable=False),
        sa.Column("latest_admin_event_id", sa.Integer(), nullable=False),
        sa.Column("created_at", instant(), nullable=False),
        sa.Column("updated_at", instant(), nullable=False),
        sa.CheckConstraint(
            "category IN ('content','pronunciation','display','function')",
            name="ck_feedback_category",
        ),
        sa.CheckConstraint(
            "status IN ('pending','processing','needs_info','resolved')", name="ck_feedback_status"
        ),
        sa.CheckConstraint("source IN ('profile','scene')", name="ck_feedback_source"),
    )
    op.create_index("ix_feedback_owner_updated", "feedbacks", ["user_id", "updated_at"])
    op.create_index("ix_feedback_status_updated", "feedbacks", ["status", "updated_at"])
    op.create_table(
        "feedback_events",
        sa.Column("feedback_id", sa.String(36), sa.ForeignKey("feedbacks.id"), primary_key=True),
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor", sa.String(16), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("text_cipher", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=True),
        sa.Column("created_at", instant(), nullable=False),
        sa.CheckConstraint("actor IN ('user','admin')", name="ck_feedback_event_actor"),
    )
    op.create_table(
        "feedback_reads",
        sa.Column("feedback_id", sa.String(36), sa.ForeignKey("feedbacks.id"), primary_key=True),
        sa.Column("role", sa.String(16), primary_key=True),
        sa.Column("actor_id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.CheckConstraint("role IN ('mini','admin')", name="ck_feedback_read_role"),
    )
    op.create_table(
        "feedback_images",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("feedback_id", sa.String(36), nullable=True),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("event_position", sa.Integer(), nullable=True),
        sa.Column("storage_key", sa.String(255), nullable=False, unique=True),
        sa.Column("content_type", sa.String(32), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("created_at", instant(), nullable=False),
        sa.ForeignKeyConstraint(
            ["feedback_id", "event_id"],
            ["feedback_events.feedback_id", "feedback_events.id"],
            name="fk_feedback_image_event",
        ),
    )
    op.create_index("ix_feedback_image_owner", "feedback_images", ["user_id"])


def downgrade():
    for table in ["feedback_images", "feedback_reads", "feedback_events", "feedbacks"]:
        op.drop_table(table)
