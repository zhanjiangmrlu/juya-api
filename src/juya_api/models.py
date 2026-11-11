"""Shared persistence with database-enforced identity and operation uniqueness."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime, utc_now


def identifier() -> str:
    """Return a stable opaque business identifier."""
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("app_id", "openid_digest", name="uq_user_wechat"),
        UniqueConstraint("user_number", name="uq_user_number"),
        CheckConstraint("user_number > 0", name="ck_user_number_positive"),
        {"comment": "小程序用户及加密联系方式"},
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="用户内部标识（UUID）"
    )
    user_number: Mapped[int] = mapped_column(
        Integer, comment="用户展示编号的持久正整数序号，用于生成Juya编号"
    )
    app_id: Mapped[str] = mapped_column(String(64), comment="所属微信小程序AppID")
    openid_digest: Mapped[str] = mapped_column(
        String(64), comment="微信OpenID的带密钥HMAC-SHA256查找摘要，不保存OpenID原文"
    )
    nickname: Mapped[str] = mapped_column(String(80), default="学习者", comment="用户昵称")
    avatar_id: Mapped[str | None] = mapped_column(
        String(36), comment="头像媒体标识；空表示使用默认头像"
    )
    phone_cipher: Mapped[str | None] = mapped_column(Text, comment="手机号Fernet密文；空表示未填写")
    phone_digest: Mapped[str | None] = mapped_column(
        String(64), index=True, comment="手机号带密钥HMAC-SHA256查找摘要；空表示未填写"
    )
    phone_source: Mapped[str | None] = mapped_column(
        String(32), comment="手机号来源：user_entered_unverified表示用户自行填写且未经验证"
    )
    wechat_cipher: Mapped[str | None] = mapped_column(
        Text, comment="用户填写的微信号Fernet密文；空表示未填写"
    )
    wechat_digest: Mapped[str | None] = mapped_column(
        String(64), index=True, comment="微信号带密钥HMAC-SHA256查找摘要；空表示未填写"
    )
    wechat_source: Mapped[str | None] = mapped_column(
        String(32), comment="微信号来源：user_entered_unverified表示用户自行填写且未经验证"
    )
    profile_version: Mapped[int] = mapped_column(
        Integer, default=1, comment="昵称和头像资料的并发修改版本号"
    )
    contact_version: Mapped[int] = mapped_column(
        Integer, default=1, comment="联系方式的并发修改版本号"
    )
    registered_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utc_now, index=True, comment="注册时间（UTC，微秒精度）"
    )
    last_login_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utc_now, comment="最近登录时间（UTC，微秒精度）"
    )
    profile_updated_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, comment="最近修改昵称或头像时间（UTC）；空表示尚未修改"
    )
    contact_updated_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, comment="最近修改联系方式时间（UTC）；空表示尚未修改"
    )


class Administrator(Base):
    __tablename__ = "administrators"
    __table_args__ = {"comment": "管理后台管理员账号"}
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    username: Mapped[str] = mapped_column(
        String(80), unique=True, comment="管理员登录用户名，库内唯一"
    )
    password_hash: Mapped[str] = mapped_column(
        Text, comment="管理员密码的Argon2哈希，不保存密码原文"
    )


class AdminSession(Base):
    __tablename__ = "admin_sessions"
    __table_args__ = {"comment": "管理后台登录会话与CSRF凭据"}
    token_digest: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="会话或访问令牌的SHA-256摘要，不保存令牌原文"
    )
    admin_id: Mapped[str] = mapped_column(
        ForeignKey("administrators.id"), comment="操作管理员标识，关联administrators.id"
    )
    csrf_digest: Mapped[str] = mapped_column(
        String(64), comment="CSRF令牌的SHA-256摘要，用于请求校验"
    )
    csrf_cipher: Mapped[str] = mapped_column(Text, comment="可恢复的CSRF令牌Fernet密文")
    expires_at: Mapped[datetime] = mapped_column(
        UTCDateTime, index=True, comment="过期时间（UTC，微秒精度）"
    )


class MiniSession(Base):
    __tablename__ = "mini_sessions"
    __table_args__ = {"comment": "小程序用户登录会话"}
    token_digest: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="会话或访问令牌的SHA-256摘要，不保存令牌原文"
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), index=True, comment="所属用户内部标识，关联users.id"
    )
    expires_at: Mapped[datetime] = mapped_column(
        UTCDateTime, index=True, comment="过期时间（UTC，微秒精度）"
    )


class LoginOperation(Base):
    __tablename__ = "login_operations"
    __table_args__ = {"comment": "微信登录幂等操作及加密结果"}
    key_digest: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="幂等键的SHA-256摘要"
    )
    fingerprint: Mapped[str] = mapped_column(
        String(64), comment="规范化请求的SHA-256指纹，用于拒绝同键不同请求"
    )
    result_cipher: Mapped[str] = mapped_column(
        Text, comment="微信登录结果的Fernet密文，用于幂等重放"
    )
    expires_at: Mapped[datetime] = mapped_column(
        UTCDateTime, index=True, comment="过期时间（UTC，微秒精度）"
    )


class Consent(Base):
    __tablename__ = "consents"
    __table_args__ = (
        UniqueConstraint("user_id", "purpose", "confirmation_id", name="uq_consent_confirmation"),
        {"comment": "用户协议和隐私授权同意记录"},
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), index=True, comment="所属用户内部标识，关联users.id"
    )
    confirmation_id: Mapped[str | None] = mapped_column(
        String(64), comment="匿名明确确认记录的关联编号"
    )
    source: Mapped[str | None] = mapped_column(String(64), comment="用户明确确认的入口来源")
    client_confirmed_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, comment="客户端确认时间，不代替服务端接受时间"
    )
    purpose: Mapped[str] = mapped_column(String(32), comment="用户同意的授权或协议用途")
    version: Mapped[str] = mapped_column(String(64), comment="用户接受的协议版本标识")
    accepted_at: Mapped[datetime] = mapped_column(
        UTCDateTime, comment="服务端接受操作时间（UTC，微秒精度）"
    )


class LoginThrottle(Base):
    __tablename__ = "login_throttles"
    __table_args__ = {"comment": "登录请求限流窗口计数"}
    key: Mapped[str] = mapped_column(String(64), primary_key=True, comment="登录限流对象的脱敏键")
    count: Mapped[int] = mapped_column(Integer, default=0, comment="当前限流窗口内的失败计数")
    window_at: Mapped[datetime] = mapped_column(
        UTCDateTime, comment="限流窗口起始时间（UTC，微秒精度）"
    )


class Audit(Base):
    __tablename__ = "audits"
    __table_args__ = {"comment": "管理员业务操作审计记录"}
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    admin_id: Mapped[str] = mapped_column(
        ForeignKey("administrators.id"), comment="操作管理员标识，关联administrators.id"
    )
    action: Mapped[str] = mapped_column(String(64), comment="执行的业务操作名称")
    object_id: Mapped[str | None] = mapped_column(
        String(128), comment="被操作业务对象标识；空表示无单一目标对象"
    )
    occurred_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utc_now, comment="操作发生时间（UTC，微秒精度）"
    )


from .privacy_models import AnalyticsEventReceipt, AnalyticsPreference  # noqa: E402, F401
