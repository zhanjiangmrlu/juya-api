"""Account-owned optional statistics choices and durable event receipts."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime


class AnalyticsPreference(Base):
    __tablename__ = "analytics_preferences"
    __table_args__ = {"comment": "独立于登录和学习成绩的账号统计许可"}
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), primary_key=True, comment="所属稳定账号"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, comment="当前账号明确允许统计")
    scope_version: Mapped[str] = mapped_column(
        String(64), default="", comment="实际展示并同意的统计披露版本"
    )
    revision: Mapped[int] = mapped_column(Integer, default=0, comment="许可状态并发修订号")
    enabled_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, comment="本轮明确开启的服务端时间"
    )
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, comment="最后一次许可变更时间")


class AnalyticsEventReceipt(Base):
    __tablename__ = "analytics_event_receipts"
    __table_args__ = {"comment": "通过许可校验的统计事件去重收据，实际传输关闭时不创建"}
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), primary_key=True, comment="服务端确认的所属账号"
    )
    event_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="事件重试不变的标识"
    )
    fingerprint: Mapped[str] = mapped_column(String(64), comment="规范化事件指纹")
    consent_revision: Mapped[int] = mapped_column(Integer, comment="事件发生时的许可修订号")
    payload: Mapped[dict] = mapped_column(JSON, comment="仅包含白名单字段的事件")
    accepted_at: Mapped[datetime] = mapped_column(UTCDateTime, comment="服务端接受时间")
