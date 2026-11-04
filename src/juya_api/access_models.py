"""Independent learning grants and an explicitly activated global free policy."""

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime
from .models import identifier


class FreePolicy(Base):
    __tablename__ = "learning_free_policy"
    __table_args__ = {
        "comment": "场景免费策略历史配置及当前策略版本；当前免费资格以cards.is_free为准"
    }
    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="策略单例标识，固定为1")
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="0",
        comment="旧版免费策略启用标志；当前资格使用场景独立免费标志",
    )
    free_count: Mapped[int | None] = mapped_column(
        Integer, comment="旧版按数量选取免费场景的配置；当前已停用，仅保留历史值"
    )
    revision: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="并发修改校验版本号"
    )


class LearningAuthorization(Base):
    __tablename__ = "learning_authorizations"
    __table_args__ = {"comment": "用户统一学习授权及有效日期"}
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), primary_key=True, comment="所属用户内部标识，关联users.id"
    )
    starts_on: Mapped[date | None] = mapped_column(
        Date, comment="授权开始的北京时间自然日；空表示尚无授权"
    )
    expires_on: Mapped[date | None] = mapped_column(
        Date, index=True, comment="授权到期的北京时间自然日，当天结束后失效；空表示无到期日"
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, comment="授权撤销时间（UTC）；空表示未撤销"
    )
    revision: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="并发修改校验版本号"
    )


class AccessHistory(Base):
    __tablename__ = "learning_access_history"
    __table_args__ = {"comment": "管理员学习授权或免费配置变更审计快照"}
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), index=True, comment="授权变更目标用户标识；全局免费配置变更时可为空"
    )
    admin_id: Mapped[str] = mapped_column(
        ForeignKey("administrators.id"), comment="操作管理员标识，关联administrators.id"
    )
    action: Mapped[str] = mapped_column(String(32), comment="执行的业务操作名称")
    before: Mapped[dict] = mapped_column(JSON, comment="变更前授权或免费配置JSON快照")
    after: Mapped[dict] = mapped_column(JSON, comment="变更后授权或免费配置JSON快照")
    occurred_at: Mapped[datetime] = mapped_column(
        UTCDateTime, comment="操作发生时间（UTC，微秒精度）"
    )
