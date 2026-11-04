"""Admin-only lifecycle receipts and original upload names, independent of mini ORM."""

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime
from .models import identifier


class AdminActionBatch(Base):
    __tablename__ = "admin_action_batches"
    __table_args__ = {"comment": "管理员批量下架或删除操作批次"}
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    admin_id: Mapped[str] = mapped_column(
        ForeignKey("administrators.id"), index=True, comment="操作管理员标识，关联administrators.id"
    )
    action: Mapped[str] = mapped_column(String(16), comment="批量操作：offline下架或delete删除")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, comment="创建时间（UTC，微秒精度）")


class AdminActionItem(Base):
    __tablename__ = "admin_action_items"
    __table_args__ = (
        UniqueConstraint("batch_id", "card_id", name="uq_admin_action_card"),
        {"comment": "批量下架或删除操作的场景快照和逐项回执"},
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("admin_action_batches.id"),
        index=True,
        comment="所属管理员批量操作标识，关联admin_action_batches.id",
    )
    card_id: Mapped[str] = mapped_column(String(36), comment="操作目标场景稳定标识，删除后保留回执")
    name: Mapped[str] = mapped_column(String(160), comment="操作确认时的场景中文名称快照")
    title_en: Mapped[str] = mapped_column(
        String(300), default="", server_default="", comment="场景英文标题快照"
    )
    revision: Mapped[int] = mapped_column(Integer, comment="操作确认绑定的场景草稿版本号")
    status: Mapped[str] = mapped_column(
        String(16), comment="确认时场景状态：draft、published、offline、deleted或missing"
    )
    version_id: Mapped[str | None] = mapped_column(String(36), comment="关联不可变发布版本标识")
    job_id: Mapped[str | None] = mapped_column(
        ForeignKey("jobs.id"), comment="关联异步处理任务标识；空表示尚无任务"
    )
    skip_reason: Mapped[str | None] = mapped_column(
        String(64), comment="跳过该场景的业务原因；空表示未跳过"
    )
    position: Mapped[int] = mapped_column(Integer, comment="项目在所属列表中的顺序位置")


class AdminMediaSource(Base):
    __tablename__ = "admin_media_sources"
    __table_args__ = {"comment": "管理员上传媒体的原始文件名"}
    media_id: Mapped[str] = mapped_column(
        ForeignKey("media.id"), primary_key=True, comment="关联媒体标识，关联media.id"
    )
    original_name: Mapped[str] = mapped_column(String(255), comment="管理员上传时的原始文件名")
