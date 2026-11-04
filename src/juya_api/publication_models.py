"""Reviewed publication batches with one durable task/result per selected card."""

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime
from .models import identifier


class PublicationBatch(Base):
    __tablename__ = "publication_batches"
    __table_args__ = {"comment": "场景批量发布的审阅批次"}
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    admin_id: Mapped[str] = mapped_column(
        ForeignKey("administrators.id"), index=True, comment="操作管理员标识，关联administrators.id"
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, comment="创建时间（UTC，微秒精度）")


class PublicationItem(Base):
    __tablename__ = "publication_items"
    __table_args__ = (
        UniqueConstraint("batch_id", "card_id", name="uq_publication_batch_card"),
        {"comment": "批量发布场景的确认快照及逐项任务"},
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("publication_batches.id"),
        index=True,
        comment="所属发布批次标识，关联publication_batches.id",
    )
    card_id: Mapped[str] = mapped_column(
        ForeignKey("cards.id"), comment="场景稳定标识，关联cards.id"
    )
    name: Mapped[str] = mapped_column(String(160), comment="发布确认时的场景中文名称快照")
    title_en: Mapped[str] = mapped_column(
        String(300), default="", server_default="", comment="场景英文标题快照"
    )
    revision: Mapped[int] = mapped_column(Integer, comment="发布确认绑定的场景草稿版本号")
    preview_id: Mapped[str] = mapped_column(
        String(36), comment="发布确认绑定的预览标识，关联publication_previews.id"
    )
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id"), comment="关联异步处理任务标识；空表示尚无任务"
    )
    position: Mapped[int] = mapped_column(Integer, comment="项目在所属列表中的顺序位置")
