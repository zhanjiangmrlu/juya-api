"""Shared persistence with database-enforced identity and operation uniqueness."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime, utc_now


def identifier() -> str:
    """Return a stable opaque business identifier."""
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("app_id", "openid_digest", name="uq_user_wechat"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    app_id: Mapped[str] = mapped_column(String(64))
    openid_digest: Mapped[str] = mapped_column(String(64))
    nickname: Mapped[str] = mapped_column(String(80), default="学习者")
    avatar_id: Mapped[str | None] = mapped_column(String(36))
    phone_cipher: Mapped[str | None] = mapped_column(Text)
    phone_digest: Mapped[str | None] = mapped_column(String(64), index=True)
    phone_source: Mapped[str | None] = mapped_column(String(32))
    wechat_cipher: Mapped[str | None] = mapped_column(Text)
    wechat_digest: Mapped[str | None] = mapped_column(String(64), index=True)
    wechat_source: Mapped[str | None] = mapped_column(String(32))
    profile_version: Mapped[int] = mapped_column(Integer, default=1)
    contact_version: Mapped[int] = mapped_column(Integer, default=1)
    registered_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, index=True)
    last_login_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    profile_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    contact_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Administrator(Base):
    __tablename__ = "administrators"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)


class AdminSession(Base):
    __tablename__ = "admin_sessions"
    token_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    admin_id: Mapped[str] = mapped_column(ForeignKey("administrators.id"))
    csrf_digest: Mapped[str] = mapped_column(String(64))
    csrf_cipher: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)


class MiniSession(Base):
    __tablename__ = "mini_sessions"
    token_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)


class LoginOperation(Base):
    __tablename__ = "login_operations"
    key_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    result_cipher: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)


class Consent(Base):
    __tablename__ = "consents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(32))
    version: Mapped[str] = mapped_column(String(64))
    accepted_at: Mapped[datetime] = mapped_column(UTCDateTime)


class LoginThrottle(Base):
    __tablename__ = "login_throttles"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    window_at: Mapped[datetime] = mapped_column(UTCDateTime)


class Audit(Base):
    __tablename__ = "audits"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    admin_id: Mapped[str] = mapped_column(ForeignKey("administrators.id"))
    action: Mapped[str] = mapped_column(String(64))
    object_id: Mapped[str | None] = mapped_column(String(128))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
