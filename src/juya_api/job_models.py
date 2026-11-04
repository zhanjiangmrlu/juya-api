"""Database-backed task acceptance, dispatch recovery and fenced worker leases."""

from datetime import datetime

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime
from .models import identifier


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = {"comment": "场景和发音等通用持久任务、重试及工作租约"}
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    kind: Mapped[str] = mapped_column(
        String(40), comment="异步任务类型，如import.parse、import.save、media.decode或发音合成"
    )
    owner_kind: Mapped[str] = mapped_column(
        String(16), comment="任务所属角色：admin管理端或mini小程序端"
    )
    owner_id: Mapped[str] = mapped_column(
        String(36), index=True, comment="所属角色或资源的内部标识"
    )
    payload: Mapped[str] = mapped_column(Text, comment="任务执行所需参数的JSON字符串")
    state: Mapped[str] = mapped_column(
        String(16),
        default="queued",
        index=True,
        comment="任务状态：queued待执行、running执行中、retry待重试、succeeded成功、failed失败",
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, comment="已领取执行的次数")
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, comment="允许的最大执行次数")
    available_at: Mapped[datetime] = mapped_column(
        UTCDateTime, index=True, comment="任务最早可执行时间（UTC，微秒精度）"
    )
    dispatch_after: Mapped[datetime] = mapped_column(
        UTCDateTime, index=True, comment="任务下次允许投递队列的时间（UTC，微秒精度）"
    )
    lease: Mapped[str | None] = mapped_column(
        String(36), comment="当前工作进程持有的租约令牌，防止过期执行覆盖结果"
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, comment="当前任务租约过期时间（UTC，微秒精度）"
    )
    error_code: Mapped[str | None] = mapped_column(
        String(64), comment="最近处理错误的业务代码；空表示无错误"
    )
    result: Mapped[dict | None] = mapped_column(
        JSON, comment="异步任务的执行结果JSON；尚无结果时为空"
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, comment="创建时间（UTC，微秒精度）")
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, comment="最近更新时间（UTC，微秒精度）"
    )
