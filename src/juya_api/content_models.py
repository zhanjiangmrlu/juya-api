"""Stable cards, editable candidates, immutable publications and private media."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, utc_now
from .models import identifier


class Card(Base):
    __tablename__ = "cards"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    current_version_id: Mapped[str | None] = mapped_column(String(36))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)


class CardDraft(Base):
    __tablename__ = "card_drafts"
    card_id: Mapped[str] = mapped_column(ForeignKey("cards.id"), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    payload: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class CardVersion(Base):
    __tablename__ = "card_versions"
    __table_args__ = (UniqueConstraint("card_id", "number", name="uq_card_publication"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    card_id: Mapped[str] = mapped_column(ForeignKey("cards.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    published_at: Mapped[datetime] = mapped_column(DateTime)


class Preview(Base):
    __tablename__ = "publication_previews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    card_id: Mapped[str] = mapped_column(ForeignKey("cards.id"), index=True)
    draft_revision: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    admin_id: Mapped[str] = mapped_column(ForeignKey("administrators.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class Media(Base):
    __tablename__ = "media"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    owner_kind: Mapped[str] = mapped_column(String(16))
    owner_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(16), default="ready")
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str] = mapped_column(String(80))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    duration: Mapped[float | None] = mapped_column(Float)
    thumbnail_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class MediaTicket(Base):
    __tablename__ = "media_tickets"
    token_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_digest: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("cards.id"))
    version_id: Mapped[str] = mapped_column(ForeignKey("card_versions.id"))
    media_id: Mapped[str] = mapped_column(ForeignKey("media.id"))
    purpose: Mapped[str] = mapped_column(String(16), default="content", server_default="content")
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class Operation(Base):
    __tablename__ = "operations"
    scope: Mapped[str] = mapped_column(String(64), primary_key=True)
    key_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    action: Mapped[str] = mapped_column(String(160))
    fingerprint: Mapped[str] = mapped_column(String(64))
    result: Mapped[str] = mapped_column(JSON)
    accepted_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class SettingCounter(Base):
    __tablename__ = "setting_counters"
    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, default=0)
