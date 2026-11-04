"""阅读开始与本次来源顺序，不参与完成和打卡统计"""

from datetime import date, datetime

from sqlalchemy import JSON, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime
from .models import identifier


class ReadingStart(Base):
    __tablename__ = "reading_starts"
    __table_args__ = {"comment": "用户场景阅读开始记录和阅读位置，不计作完成或打卡"}
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), primary_key=True, comment="所属用户内部标识，关联users.id"
    )
    card_id: Mapped[str] = mapped_column(
        ForeignKey("cards.id"), primary_key=True, comment="场景稳定标识，关联cards.id"
    )
    started_at: Mapped[datetime] = mapped_column(
        UTCDateTime, comment="阅读开始时间（UTC，微秒精度）"
    )
    position: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="客户端保存的场景阅读位置JSON；空表示无位置快照"
    )


class LearningQueue(Base):
    __tablename__ = "learning_queues"
    __table_args__ = {"comment": "用户本轮场景学习队列及来源快照"}
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), index=True, comment="所属用户内部标识，关联users.id"
    )
    source: Mapped[str] = mapped_column(
        String(16), comment="队列来源：learning学习、favorites收藏、records记录、day指定日期"
    )
    day: Mapped[date | None] = mapped_column(
        Date, comment="来源为day时的北京时间学习日期；其他来源为空"
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, comment="创建时间（UTC，微秒精度）")
    expires_at: Mapped[datetime] = mapped_column(
        UTCDateTime, index=True, comment="过期时间（UTC，微秒精度）"
    )


class LearningQueueItem(Base):
    __tablename__ = "learning_queue_items"
    __table_args__ = {"comment": "学习队列内场景的固定顺序"}
    queue_id: Mapped[str] = mapped_column(
        ForeignKey("learning_queues.id"),
        primary_key=True,
        comment="所属学习队列标识，关联learning_queues.id",
    )
    position: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="项目在所属列表中的顺序位置"
    )
    card_id: Mapped[str] = mapped_column(
        ForeignKey("cards.id"), comment="场景稳定标识，关联cards.id"
    )
