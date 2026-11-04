"""Learning history remains attached to stable users/cards after business deletion."""

from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime


class Completion(Base):
    __tablename__ = "completions"
    __table_args__ = {"comment": "用户场景首次和最近完成事实"}
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), primary_key=True, comment="所属用户内部标识，关联users.id"
    )
    card_id: Mapped[str] = mapped_column(
        ForeignKey("cards.id"), primary_key=True, comment="场景稳定标识，关联cards.id"
    )
    first_completed_at: Mapped[datetime] = mapped_column(
        UTCDateTime, comment="首次完成时间（UTC，微秒精度）"
    )
    last_completed_at: Mapped[datetime] = mapped_column(
        UTCDateTime, index=True, comment="最近完成时间（UTC，微秒精度）"
    )
    first_version_id: Mapped[str] = mapped_column(
        ForeignKey("card_versions.id"), comment="首次完成时的不可变发布版本标识"
    )
    last_version_id: Mapped[str] = mapped_column(
        ForeignKey("card_versions.id"), comment="最近完成时的不可变发布版本标识"
    )
    safe_name: Mapped[str] = mapped_column(
        String(160), comment="首次完成时保存的安全场景名称快照，供历史记录展示"
    )
    thumbnail_id: Mapped[str | None] = mapped_column(
        String(36), comment="缩略图媒体标识；空表示无缩略图"
    )


class DailyLearning(Base):
    __tablename__ = "daily_learning"
    __table_args__ = {"comment": "按北京时间自然日记录的场景学习事实"}
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), primary_key=True, comment="所属用户内部标识，关联users.id"
    )
    card_id: Mapped[str] = mapped_column(
        ForeignKey("cards.id"), primary_key=True, comment="场景稳定标识，关联cards.id"
    )
    date: Mapped[date] = mapped_column(
        Date, primary_key=True, index=True, comment="学习事实所属北京时间自然日"
    )
    accepted_at: Mapped[datetime] = mapped_column(
        UTCDateTime, comment="服务端接受操作时间（UTC，微秒精度）"
    )
    version_id: Mapped[str] = mapped_column(
        ForeignKey("card_versions.id"), comment="关联不可变发布版本标识"
    )


class Checkin(Base):
    __tablename__ = "checkins"
    __table_args__ = {"comment": "用户按北京时间自然日记录的学习打卡"}
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), primary_key=True, comment="所属用户内部标识，关联users.id"
    )
    date: Mapped[date] = mapped_column(
        Date, primary_key=True, index=True, comment="学习事实所属北京时间自然日"
    )
    accepted_at: Mapped[datetime] = mapped_column(
        UTCDateTime, comment="服务端接受操作时间（UTC，微秒精度）"
    )


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = {"comment": "用户场景收藏关系"}
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), primary_key=True, comment="所属用户内部标识，关联users.id"
    )
    card_id: Mapped[str] = mapped_column(
        ForeignKey("cards.id"), primary_key=True, comment="场景稳定标识，关联cards.id"
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, index=True, comment="创建时间（UTC，微秒精度）"
    )
