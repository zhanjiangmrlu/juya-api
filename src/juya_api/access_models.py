"""Independent learning grants and an explicitly activated global free policy."""

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime
from .models import identifier


class FreePolicy(Base):
    __tablename__ = "learning_free_policy"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    free_count: Mapped[int | None] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class LearningAuthorization(Base):
    __tablename__ = "learning_authorizations"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    starts_on: Mapped[date | None] = mapped_column(Date)
    expires_on: Mapped[date | None] = mapped_column(Date, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class AccessHistory(Base):
    __tablename__ = "learning_access_history"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    admin_id: Mapped[str] = mapped_column(ForeignKey("administrators.id"))
    action: Mapped[str] = mapped_column(String(32))
    before: Mapped[dict] = mapped_column(JSON)
    after: Mapped[dict] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
