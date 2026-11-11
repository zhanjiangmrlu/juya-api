"""Immutable selected sets and per-content durable free mutation receipts."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime
from .models import identifier


class FreeAccessBatch(Base):
    __tablename__ = "free_access_batches"
    __table_args__ = {"comment": "跨页免费设置任务及冻结选择"}
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="批次标识"
    )
    admin_id: Mapped[str] = mapped_column(ForeignKey("administrators.id"), comment="操作管理员")
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), unique=True, comment="持久任务标识")
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("free_access_batches.id"), comment="失败重试的原批次"
    )
    content_type: Mapped[str] = mapped_column(String(16), comment="内容类型scene或listening")
    is_free: Mapped[bool] = mapped_column(Boolean, comment="目标免费状态")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, comment="接受时间UTC")


class FreeAccessBatchItem(Base):
    __tablename__ = "free_access_batch_items"
    __table_args__ = {"comment": "完整选择名单、预览快照及逐项执行回执"}
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("free_access_batches.id"), primary_key=True, comment="所属批次"
    )
    content_id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="稳定内容标识")
    position: Mapped[int] = mapped_column(Integer, comment="原选择顺序")
    snapshot: Mapped[dict] = mapped_column(JSON, comment="确认前已展示的发布及免费版本快照")
    status: Mapped[str] = mapped_column(
        String(16), comment="逐项状态：pending待处理、succeeded成功、skipped跳过、failed失败"
    )
    reason: Mapped[str | None] = mapped_column(String(64), comment="跳过或失败原因码")
    message: Mapped[str | None] = mapped_column(String(300), comment="完整原因说明")
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, comment="逐项完成时间UTC")
