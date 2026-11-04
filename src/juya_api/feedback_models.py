"""Private append-only feedback with per-thread server order and per-actor read watermarks."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime
from .models import identifier


class Feedback(Base):
    __tablename__ = "feedbacks"
    __table_args__ = (
        CheckConstraint(
            "category IN ('content','pronunciation','display','function')",
            name="ck_feedback_category",
        ),
        CheckConstraint(
            "status IN ('pending','processing','needs_info','resolved')", name="ck_feedback_status"
        ),
        CheckConstraint("source IN ('profile','scene')", name="ck_feedback_source"),
        Index("ix_feedback_owner_updated", "user_id", "updated_at"),
        Index("ix_feedback_status_updated", "status", "updated_at"),
        {"comment": "用户反馈主线程及加密摘要"},
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), comment="所属用户内部标识，关联users.id"
    )
    category: Mapped[str] = mapped_column(
        String(16), comment="反馈类别：content内容、pronunciation发音、display显示、function功能"
    )
    status: Mapped[str] = mapped_column(
        String(16),
        comment="处理状态：pending待处理、processing处理中、needs_info待补充、resolved已解决",
    )
    summary_cipher: Mapped[str] = mapped_column(Text, comment="反馈摘要Fernet密文")
    source: Mapped[str] = mapped_column(String(16), comment="反馈入口：profile账号页或scene场景页")
    card_id: Mapped[str | None] = mapped_column(
        String(36), comment="反馈关联场景标识；账号页反馈可为空"
    )
    version_id: Mapped[str | None] = mapped_column(
        String(36), comment="反馈发生时的场景发布版本标识；可为空"
    )
    source_title: Mapped[str | None] = mapped_column(
        String(160), comment="反馈来源的中文场景标题快照"
    )
    source_title_en: Mapped[str] = mapped_column(
        String(300), default="", comment="反馈来源的英文场景标题快照"
    )
    latest_event_id: Mapped[int] = mapped_column(Integer, default=0, comment="线程最近事件序号")
    latest_user_event_id: Mapped[int] = mapped_column(
        Integer, default=0, comment="最近一条用户事件序号"
    )
    latest_admin_event_id: Mapped[int] = mapped_column(
        Integer, default=0, comment="最近一条管理员事件序号"
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, comment="创建时间（UTC，微秒精度）")
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, comment="最近更新时间（UTC，微秒精度）"
    )


class FeedbackEvent(Base):
    __tablename__ = "feedback_events"
    __table_args__ = (
        CheckConstraint("actor IN ('user','admin')", name="ck_feedback_event_actor"),
        {"comment": "反馈线程内追加事件及加密消息"},
    )
    feedback_id: Mapped[str] = mapped_column(
        ForeignKey("feedbacks.id"), primary_key=True, comment="所属反馈线程标识，关联feedbacks.id"
    )
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="线程内按服务端顺序递增的事件序号"
    )
    actor: Mapped[str] = mapped_column(String(16), comment="事件发起角色：user用户或admin管理员")
    actor_id: Mapped[str] = mapped_column(String(36), comment="事件发起用户或管理员的内部标识")
    text_cipher: Mapped[str | None] = mapped_column(
        Text, comment="反馈消息Fernet密文；仅状态变更时可为空"
    )
    status: Mapped[str | None] = mapped_column(
        String(16), comment="该事件设置的新反馈处理状态；未变更状态时为空"
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, comment="创建时间（UTC，微秒精度）")


class FeedbackRead(Base):
    __tablename__ = "feedback_reads"
    __table_args__ = (
        CheckConstraint("role IN ('mini','admin')", name="ck_feedback_read_role"),
        {"comment": "反馈参与者的已读事件水位"},
    )
    feedback_id: Mapped[str] = mapped_column(
        ForeignKey("feedbacks.id"), primary_key=True, comment="所属反馈线程标识，关联feedbacks.id"
    )
    role: Mapped[str] = mapped_column(
        String(16), primary_key=True, comment="阅读者角色：mini小程序用户或admin管理员"
    )
    actor_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, comment="阅读者用户或管理员内部标识"
    )
    event_id: Mapped[int] = mapped_column(Integer, comment="该阅读者已读到的最大线程事件序号")


class FeedbackImage(Base):
    __tablename__ = "feedback_images"
    __table_args__ = (
        ForeignKeyConstraint(
            ["feedback_id", "event_id"],
            ["feedback_events.feedback_id", "feedback_events.id"],
            name="fk_feedback_image_event",
        ),
        Index("ix_feedback_image_owner", "user_id"),
        {"comment": "反馈图片及所关联的消息事件"},
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), comment="所属用户内部标识，关联users.id"
    )
    feedback_id: Mapped[str | None] = mapped_column(
        String(36), comment="绑定的反馈线程标识；尚未提交时为空"
    )
    event_id: Mapped[int | None] = mapped_column(
        Integer, comment="绑定的反馈消息事件序号；尚未提交时为空"
    )
    event_position: Mapped[int | None] = mapped_column(
        Integer, comment="图片在同一反馈消息内的展示位置"
    )
    storage_key: Mapped[str] = mapped_column(String(255), unique=True, comment="私有存储对象键")
    content_type: Mapped[str] = mapped_column(String(32), comment="媒体MIME类型")
    sha256: Mapped[str] = mapped_column(String(64), comment="文件原始字节的SHA-256摘要")
    size: Mapped[int] = mapped_column(Integer, comment="文件大小（字节）")
    width: Mapped[int] = mapped_column(Integer, comment="图片宽度（像素）；空表示不适用")
    height: Mapped[int] = mapped_column(Integer, comment="图片高度（像素）；空表示不适用")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, comment="创建时间（UTC，微秒精度）")
