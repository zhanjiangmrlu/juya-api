"""阅读开始与本次来源顺序，不参与完成和打卡统计"""

from datetime import date, datetime

from sqlalchemy import JSON, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime
from .models import identifier


class ReadingStart(Base):
    __tablename__ = "reading_starts"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("cards.id"), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime)
    position: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class LearningQueue(Base):
    __tablename__ = "learning_queues"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    source: Mapped[str] = mapped_column(String(16))
    day: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)


class LearningQueueItem(Base):
    __tablename__ = "learning_queue_items"
    queue_id: Mapped[str] = mapped_column(ForeignKey("learning_queues.id"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("cards.id"))
