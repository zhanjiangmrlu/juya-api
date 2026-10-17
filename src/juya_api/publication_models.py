"""Reviewed publication batches with one durable task/result per selected card."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base
from .models import identifier


class PublicationBatch(Base):
    __tablename__ = "publication_batches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    admin_id: Mapped[str] = mapped_column(ForeignKey("administrators.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class PublicationItem(Base):
    __tablename__ = "publication_items"
    __table_args__ = (UniqueConstraint("batch_id", "card_id", name="uq_publication_batch_card"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    batch_id: Mapped[str] = mapped_column(ForeignKey("publication_batches.id"), index=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("cards.id"))
    name: Mapped[str] = mapped_column(String(160))
    revision: Mapped[int] = mapped_column(Integer)
    preview_id: Mapped[str] = mapped_column(String(36))
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    position: Mapped[int] = mapped_column(Integer)
