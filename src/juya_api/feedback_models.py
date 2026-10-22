"""Private append-only feedback with per-thread server order and per-actor read watermarks."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime
from .models import identifier


class Feedback(Base):
    __tablename__ = "feedbacks"
    __table_args__ = (
        CheckConstraint(
            "category IN ('content','pronunciation','display','function')",
            name="ck_feedback_category",
        ),
        CheckConstraint(
            "status IN ('pending','processing','needs_info','resolved')", name="ck_feedback_status"
        ),
        CheckConstraint("source IN ('profile','scene')", name="ck_feedback_source"),
        Index("ix_feedback_owner_updated", "user_id", "updated_at"),
        Index("ix_feedback_status_updated", "status", "updated_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    category: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    summary_cipher: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16))
    card_id: Mapped[str | None] = mapped_column(String(36))
    version_id: Mapped[str | None] = mapped_column(String(36))
    source_title: Mapped[str | None] = mapped_column(String(160))
    source_title_en: Mapped[str] = mapped_column(String(300), default="")
    latest_event_id: Mapped[int] = mapped_column(Integer, default=0)
    latest_user_event_id: Mapped[int] = mapped_column(Integer, default=0)
    latest_admin_event_id: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)


class FeedbackEvent(Base):
    __tablename__ = "feedback_events"
    __table_args__ = (CheckConstraint("actor IN ('user','admin')", name="ck_feedback_event_actor"),)
    feedback_id: Mapped[str] = mapped_column(ForeignKey("feedbacks.id"), primary_key=True)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[str] = mapped_column(String(36))
    text_cipher: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)


class FeedbackRead(Base):
    __tablename__ = "feedback_reads"
    __table_args__ = (CheckConstraint("role IN ('mini','admin')", name="ck_feedback_read_role"),)
    feedback_id: Mapped[str] = mapped_column(ForeignKey("feedbacks.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer)


class FeedbackImage(Base):
    __tablename__ = "feedback_images"
    __table_args__ = (
        ForeignKeyConstraint(
            ["feedback_id", "event_id"],
            ["feedback_events.feedback_id", "feedback_events.id"],
            name="fk_feedback_image_event",
        ),
        Index("ix_feedback_image_owner", "user_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    feedback_id: Mapped[str | None] = mapped_column(String(36))
    event_id: Mapped[int | None] = mapped_column(Integer)
    event_position: Mapped[int | None] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str] = mapped_column(String(32))
    sha256: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
