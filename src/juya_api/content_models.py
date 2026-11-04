"""Stable cards, editable candidates, immutable publications and private media."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime, utc_now
from .models import identifier


class Card(Base):
    __tablename__ = "cards"
    __table_args__ = {"comment": "雅思词汇场景的稳定身份与发布状态"}
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    status: Mapped[str] = mapped_column(
        String(16),
        default="draft",
        index=True,
        comment="场景状态：draft草稿、published已发布、offline已下架",
    )
    is_free: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="0",
        comment="是否对未获学习授权用户免费开放（0否，1是）",
    )
    free_revision: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", comment="当前免费资格的并发校验版本号"
    )
    current_version_id: Mapped[str | None] = mapped_column(
        String(36), comment="当前已发布场景版本标识；空表示从未发布"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, index=True, comment="排序值，按升序展示"
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utc_now, comment="创建时间（UTC，微秒精度）"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, index=True, comment="软删除时间（UTC，微秒精度）；空表示未删除"
    )


class CardDraft(Base):
    __tablename__ = "card_drafts"
    __table_args__ = {"comment": "场景当前可编辑草稿"}
    card_id: Mapped[str] = mapped_column(
        ForeignKey("cards.id"), primary_key=True, comment="场景稳定标识，关联cards.id"
    )
    revision: Mapped[int] = mapped_column(Integer, default=1, comment="并发修改校验版本号")
    payload: Mapped[dict] = mapped_column(
        JSON, comment="场景当前草稿内容JSON，包含中英文资料、词汇及媒体引用"
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utc_now, comment="最近更新时间（UTC，微秒精度）"
    )


class CardVersion(Base):
    __tablename__ = "card_versions"
    __table_args__ = (
        UniqueConstraint("card_id", "number", name="uq_card_publication"),
        {"comment": "场景不可变已发布版本"},
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    card_id: Mapped[str] = mapped_column(
        ForeignKey("cards.id"), index=True, comment="场景稳定标识，关联cards.id"
    )
    number: Mapped[int] = mapped_column(Integer, comment="同一场景内递增的发布版本序号")
    payload: Mapped[dict] = mapped_column(
        JSON, comment="场景不可变发布内容JSON，包含中英文资料、词汇及媒体引用"
    )
    content_hash: Mapped[str] = mapped_column(
        String(64), comment="规范化内容的SHA-256摘要，用于校验内容一致性"
    )
    published_at: Mapped[datetime] = mapped_column(
        UTCDateTime, comment="版本发布时间（UTC，微秒精度）"
    )


class Preview(Base):
    __tablename__ = "publication_previews"
    __table_args__ = {"comment": "绑定草稿版本和内容摘要的发布预览凭据"}
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    card_id: Mapped[str] = mapped_column(
        ForeignKey("cards.id"), index=True, comment="场景稳定标识，关联cards.id"
    )
    draft_revision: Mapped[int] = mapped_column(
        Integer, comment="预览绑定的草稿版本号，用于阻止过期预览发布"
    )
    content_hash: Mapped[str] = mapped_column(
        String(64), comment="规范化内容的SHA-256摘要，用于校验内容一致性"
    )
    admin_id: Mapped[str] = mapped_column(
        ForeignKey("administrators.id"), comment="操作管理员标识，关联administrators.id"
    )
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, comment="过期时间（UTC，微秒精度）")


class Media(Base):
    __tablename__ = "media"
    __table_args__ = {"comment": "私有媒体及处理产物元数据"}
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    owner_kind: Mapped[str] = mapped_column(String(16), comment="所属业务角色或资源域")
    owner_id: Mapped[str] = mapped_column(
        String(36), index=True, comment="所属角色或资源的内部标识"
    )
    kind: Mapped[str] = mapped_column(
        String(16),
        comment="媒体类型，如image图片、audio原音频、avatar头像、thumbnail缩略图、audio_playback转码音频、pronunciation发音",
    )
    state: Mapped[str] = mapped_column(
        String(16), default="ready", comment="媒体状态：processing处理中、ready可用、failed失败"
    )
    job_id: Mapped[str | None] = mapped_column(
        String(36), index=True, comment="关联异步处理任务标识；空表示尚无任务"
    )
    storage_key: Mapped[str] = mapped_column(String(255), unique=True, comment="私有存储对象键")
    content_type: Mapped[str] = mapped_column(String(80), comment="媒体MIME类型")
    size: Mapped[int] = mapped_column(Integer, comment="文件大小（字节）")
    sha256: Mapped[str] = mapped_column(String(64), index=True, comment="文件原始字节的SHA-256摘要")
    width: Mapped[int | None] = mapped_column(Integer, comment="图片宽度（像素）；空表示不适用")
    height: Mapped[int | None] = mapped_column(Integer, comment="图片高度（像素）；空表示不适用")
    duration: Mapped[float | None] = mapped_column(
        Float, comment="音频时长（秒）；空表示不适用或尚未解析"
    )
    thumbnail_id: Mapped[str | None] = mapped_column(
        String(36), comment="缩略图媒体标识；空表示无缩略图"
    )
    playback_id: Mapped[str | None] = mapped_column(
        String(36), comment="浏览器或小程序可播放的转码音频媒体标识"
    )
    processing_stage: Mapped[str | None] = mapped_column(
        String(24), comment="媒体解析或转码的当前处理阶段"
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utc_now, comment="创建时间（UTC，微秒精度）"
    )


class MediaTicket(Base):
    __tablename__ = "media_tickets"
    __table_args__ = {"comment": "绑定用户会话和场景版本的临时媒体访问凭据"}
    token_digest: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="会话或访问令牌的SHA-256摘要，不保存令牌原文"
    )
    session_digest: Mapped[str] = mapped_column(
        String(64), comment="获发访问票据的小程序登录会话摘要"
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), index=True, comment="所属用户内部标识，关联users.id"
    )
    card_id: Mapped[str] = mapped_column(
        ForeignKey("cards.id"), comment="场景稳定标识，关联cards.id"
    )
    version_id: Mapped[str] = mapped_column(
        ForeignKey("card_versions.id"), comment="关联不可变发布版本标识"
    )
    media_id: Mapped[str] = mapped_column(
        ForeignKey("media.id"), comment="关联媒体标识，关联media.id"
    )
    purpose: Mapped[str] = mapped_column(
        String(16),
        default="content",
        server_default="content",
        comment="媒体访问用途：content正文或summary列表摘要",
    )
    expires_at: Mapped[datetime] = mapped_column(
        UTCDateTime, index=True, comment="过期时间（UTC，微秒精度）"
    )


class Operation(Base):
    __tablename__ = "operations"
    __table_args__ = {"comment": "业务写操作的持久化幂等结果"}
    scope: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="幂等键所属作用域，与键摘要共同唯一标识操作"
    )
    key_digest: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="幂等键的SHA-256摘要"
    )
    action: Mapped[str] = mapped_column(String(160), comment="执行的业务操作名称")
    fingerprint: Mapped[str] = mapped_column(
        String(64), comment="规范化请求的SHA-256指纹，用于拒绝同键不同请求"
    )
    result: Mapped[str] = mapped_column(JSON, comment="幂等操作的响应结果JSON快照")
    accepted_at: Mapped[datetime] = mapped_column(
        UTCDateTime, index=True, comment="服务端接受操作时间（UTC，微秒精度）"
    )


class SettingCounter(Base):
    __tablename__ = "setting_counters"
    __table_args__ = {"comment": "业务编号及目录、授权等版本计数器"}
    name: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        comment="计数器名称，如user_number、schema_contract或catalog_revision",
    )
    value: Mapped[int] = mapped_column(Integer, default=0, comment="对应业务序号或版本号的当前值")
