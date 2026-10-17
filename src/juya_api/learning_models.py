"""Learning history remains attached to stable users/cards after business deletion."""

from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime


class Completion(Base):
    __tablename__ = "completions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("cards.id"), primary_key=True)
    first_completed_at: Mapped[datetime] = mapped_column(UTCDateTime)
    last_completed_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    first_version_id: Mapped[str] = mapped_column(ForeignKey("card_versions.id"))
    last_version_id: Mapped[str] = mapped_column(ForeignKey("card_versions.id"))
    safe_name: Mapped[str] = mapped_column(String(160))
    thumbnail_id: Mapped[str | None] = mapped_column(String(36))


class DailyLearning(Base):
    __tablename__ = "daily_learning"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("cards.id"), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True, index=True)
    accepted_at: Mapped[datetime] = mapped_column(UTCDateTime)
    version_id: Mapped[str] = mapped_column(ForeignKey("card_versions.id"))


class Checkin(Base):
    __tablename__ = "checkins"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True, index=True)
    accepted_at: Mapped[datetime] = mapped_column(UTCDateTime)


class Favorite(Base):
    __tablename__ = "favorites"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("cards.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
