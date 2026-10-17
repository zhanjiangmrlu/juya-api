"""Request-scoped transactions and role-separated authorization."""

import hmac

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from .errors import DomainError
from .models import Administrator, AdminSession, MiniSession, User
from .security import digest

ADMIN_COOKIE = "juya_admin_session"


def database(request: Request):
    """Commit all business records together, or roll back the entire failed request."""
    with request.app.state.sessions.begin() as session:
        yield session


def administrator(request: Request, db: Session = Depends(database)) -> Administrator:
    """Require an unexpired administrator cookie and CSRF on every mutation."""
    value = request.cookies.get(ADMIN_COOKIE, "")
    session = db.get(AdminSession, digest(value)) if value.startswith("adm_") else None
    if not session or session.expires_at <= request.app.state.clock():
        raise DomainError(401, "admin_session_required", "请重新登录管理后台")
    origin = request.headers.get("origin")
    if origin and origin not in request.app.state.settings.allowed_origins:
        raise DomainError(403, "origin_rejected", "请求来源无效")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf = request.headers.get("X-CSRF-Token", "")
        if not csrf or not hmac.compare_digest(digest(csrf), session.csrf_digest):
            raise DomainError(403, "csrf_rejected", "请刷新页面后重试")
    admin = db.get(Administrator, session.admin_id)
    if not admin:
        raise DomainError(401, "admin_session_required", "请重新登录管理后台")
    return admin


def learner(request: Request, db: Session = Depends(database)) -> User:
    """Require this application's revocable learner token, never an admin cookie."""
    value = request.headers.get("Authorization", "").removeprefix("Bearer ")
    session = db.get(MiniSession, digest(value)) if value.startswith("mini_") else None
    if not session or session.expires_at <= request.app.state.clock():
        raise DomainError(401, "login_required", "请主动登录后继续")
    user = db.get(User, session.user_id)
    if not user:
        raise DomainError(401, "login_required", "请主动登录后继续")
    return user


def operation_key(request: Request) -> str:
    """Require a sufficiently long key for durable idempotency and recovery."""
    value = request.headers.get("Idempotency-Key", "")
    if not 16 <= len(value) <= 128:
        raise DomainError(422, "operation_key_required", "请重新发起操作")
    return value
