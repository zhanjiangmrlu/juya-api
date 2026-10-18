"""Admin-only lifecycle receipts and original upload names, independent of mini ORM."""

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime
from .models import identifier


class AdminActionBatch(Base):
    __tablename__ = "admin_action_batches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    admin_id: Mapped[str] = mapped_column(ForeignKey("administrators.id"), index=True)
    action: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)


class AdminActionItem(Base):
    __tablename__ = "admin_action_items"
    __table_args__ = (UniqueConstraint("batch_id", "card_id", name="uq_admin_action_card"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    batch_id: Mapped[str] = mapped_column(ForeignKey("admin_action_batches.id"), index=True)
    card_id: Mapped[str] = mapped_column(String(36))
    name: Mapped[str] = mapped_column(String(160))
    revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    version_id: Mapped[str | None] = mapped_column(String(36))
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"))
    skip_reason: Mapped[str | None] = mapped_column(String(64))
    position: Mapped[int] = mapped_column(Integer)


class AdminMediaSource(Base):
    __tablename__ = "admin_media_sources"
    media_id: Mapped[str] = mapped_column(ForeignKey("media.id"), primary_key=True)
    original_name: Mapped[str] = mapped_column(String(255))
