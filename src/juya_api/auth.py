"""Trusted WeChat identity, administrator authentication and revocable sessions."""

import json
from contextlib import suppress
from datetime import timedelta
from typing import Literal

import httpx
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import timestamp
from .dependencies import ADMIN_COOKIE, administrator, database, learner, operation_key
from .errors import DomainError
from .models import (
    Administrator,
    AdminSession,
    Consent,
    LoginOperation,
    LoginThrottle,
    MiniSession,
    User,
    identifier,
)
from .persistence import insert_once
from .security import decrypt, digest, encrypt, fingerprint, lookup, token

passwords = PasswordHasher()


def create_administrator(db: Session, username: str, password: str) -> Administrator:
    """Initialize the sole administrator through an offline provisioning command."""
    if len(password) < 12:
        raise ValueError("administrator password must have at least 12 characters")
    if db.scalar(select(Administrator.id).limit(1)):
        raise ValueError("a sole administrator already exists")
    admin = Administrator(username=username, password_hash=passwords.hash(password))
    db.add(admin)
    db.flush()
    return admin


class WechatGateway:
    def __init__(self, settings):
        self.settings = settings

    def exchange(self, code: str) -> str:
        """Redeem a temporary code only on the server; discard the session_key."""
        try:
            response = httpx.get(
                "https://api.weixin.qq.com/sns/jscode2session",
                params={
                    "appid": self.settings.wechat_app_id,
                    "secret": self.settings.wechat_app_secret,
                    "js_code": code,
                    "grant_type": "authorization_code",
                },
                timeout=10,
            )
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError):
            raise DomainError(503, "wechat_unavailable", "登录暂未成功，请重试") from None
        if result.get("errcode") or not isinstance(result.get("openid"), str):
            raise DomainError(401, "wechat_failed", "登录暂未成功，请重试")
        return result["openid"]


def user_view(user: User, settings) -> dict:
    """Expose a learner's own profile without their trusted identity or secrets."""
    return {
        "id": user.id,
        "nickname": user.nickname,
        "avatar_id": user.avatar_id,
        "phone": decrypt(settings, user.phone_cipher),
        "wechat_contact": decrypt(settings, user.wechat_cipher),
        "phone_source": user.phone_source,
        "wechat_source": user.wechat_source,
        "profile_version": user.profile_version,
        "contact_version": user.contact_version,
        "registered_at": timestamp(user.registered_at),
        "last_login_at": timestamp(user.last_login_at),
    }


class AdminLogin(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class WechatLogin(BaseModel):
    code: str = Field(min_length=1, max_length=512)
    consent: Literal[True]
    consent_version: str = Field(min_length=1, max_length=64)


def admin_routes() -> APIRouter:
    router = APIRouter(prefix="/api/admin/v1/auth", tags=["administrator authentication"])

    @router.post("/login")
    def login(
        body: AdminLogin, request: Request, response: Response, db: Session = Depends(database)
    ):
        settings, now = request.app.state.settings, request.app.state.clock()
        origin = request.headers.get("origin")
        if origin and origin not in settings.allowed_origins:
            raise DomainError(403, "origin_rejected", "请求来源无效")
        throttle_key = lookup(
            settings, "admin-login", request.client.host if request.client else ""
        )
        throttle = db.scalar(
            select(LoginThrottle).where(LoginThrottle.key == throttle_key).with_for_update()
        )
        if not throttle:
            throttle = LoginThrottle(key=throttle_key, count=0, window_at=now)
            db.add(throttle)
        if now - throttle.window_at > timedelta(minutes=15):
            throttle.count, throttle.window_at = 0, now
        if throttle.count >= 10:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {"code": "login_throttled", "message": "尝试过于频繁，请稍后重试"}
                },
            )
        admin = db.scalar(select(Administrator).where(Administrator.username == body.username))
        valid = False
        with suppress(VerificationError, InvalidHashError):
            valid = passwords.verify(admin.password_hash, body.password) if admin else False
        if not valid or admin is None:
            throttle.count += 1
            return JSONResponse(
                status_code=401,
                content={"error": {"code": "invalid_credentials", "message": "账号或密码不正确"}},
            )
        throttle.count = 0
        credential, csrf = token("adm_"), token("csrf_")
        db.add(
            AdminSession(
                token_digest=digest(credential),
                admin_id=admin.id,
                csrf_digest=digest(csrf),
                csrf_cipher=encrypt(settings, csrf),
                expires_at=now + timedelta(hours=settings.admin_session_hours),
            )
        )
        response.set_cookie(
            ADMIN_COOKIE,
            credential,
            secure=settings.cookie_secure,
            httponly=True,
            samesite="strict",
            path="/api/admin/v1",
            max_age=settings.admin_session_hours * 3600,
        )
        return {"administrator": {"id": admin.id, "username": admin.username}, "csrf_token": csrf}

    @router.get("/session")
    def session(
        request: Request,
        admin: Administrator = Depends(administrator),
        db: Session = Depends(database),
    ):
        current = db.get(AdminSession, digest(request.cookies[ADMIN_COOKIE]))
        assert current is not None
        return {
            "id": admin.id,
            "username": admin.username,
            "csrf_token": decrypt(request.app.state.settings, current.csrf_cipher),
        }

    @router.post("/logout")
    def logout(
        request: Request,
        response: Response,
        admin=Depends(administrator),
        db: Session = Depends(database),
    ):
        db.delete(db.get(AdminSession, digest(request.cookies[ADMIN_COOKIE])))
        response.delete_cookie(ADMIN_COOKIE, path="/api/admin/v1")
        return {"logged_out": True}

    return router


def mini_routes() -> APIRouter:
    router = APIRouter(prefix="/api/mini/v1", tags=["learner authentication"])

    @router.post("/auth/wechat")
    def login(
        body: WechatLogin,
        request: Request,
        key: str = Depends(operation_key),
        db: Session = Depends(database),
    ):
        settings, now = request.app.state.settings, request.app.state.clock()
        key_hash, request_hash = digest(key), fingerprint(body.model_dump())
        previous = db.get(LoginOperation, key_hash)
        if previous and previous.expires_at > now:
            if previous.fingerprint != request_hash:
                raise DomainError(409, "operation_conflict", "登录操作已变化，请重新发起")
            if not previous.result_cipher:
                raise DomainError(409, "operation_incomplete", "请重新发起登录")
            return json.loads(decrypt(settings, previous.result_cipher) or "{}")
        if previous:
            raise DomainError(409, "operation_expired", "请重新发起登录")
        insert_once(
            db,
            LoginOperation,
            {
                "key_digest": key_hash,
                "fingerprint": request_hash,
                "result_cipher": "",
                "expires_at": now + timedelta(minutes=15),
            },
            ["key_digest"],
        )
        operation = db.scalar(
            select(LoginOperation).where(LoginOperation.key_digest == key_hash).with_for_update()
        )
        assert operation is not None
        if operation.fingerprint != request_hash:
            raise DomainError(409, "operation_conflict", "登录操作已变化，请重新发起")
        if operation.result_cipher:
            return json.loads(decrypt(settings, operation.result_cipher) or "{}")
        openid = request.app.state.wechat.exchange(body.code)
        identity = lookup(settings, "openid:" + settings.wechat_app_id, openid)
        insert_once(
            db,
            User,
            {
                "id": identifier(),
                "app_id": settings.wechat_app_id,
                "openid_digest": identity,
                "registered_at": now,
                "last_login_at": now,
            },
            ["app_id", "openid_digest"],
        )
        user = db.scalar(
            select(User)
            .where(User.app_id == settings.wechat_app_id, User.openid_digest == identity)
            .with_for_update()
        )
        assert user is not None
        user.last_login_at = now
        credential = token("mini_")
        db.add(
            MiniSession(
                token_digest=digest(credential),
                user_id=user.id,
                expires_at=now + timedelta(days=settings.session_days),
            )
        )
        db.add(
            Consent(
                user_id=user.id,
                purpose="wechat_login",
                version=body.consent_version,
                accepted_at=now,
            )
        )
        result = {
            "access_token": credential,
            "expires_at": timestamp(now + timedelta(days=settings.session_days)),
            "user": user_view(user, settings),
        }
        operation.result_cipher = encrypt(settings, json.dumps(result))
        db.flush()
        return result

    @router.get("/me")
    def me(request: Request, user: User = Depends(learner)):
        return user_view(user, request.app.state.settings)

    @router.post("/auth/logout")
    def logout(request: Request, user: User = Depends(learner), db: Session = Depends(database)):
        value = request.headers["Authorization"].removeprefix("Bearer ")
        db.delete(db.get(MiniSession, digest(value)))
        return {"logged_out": True}

    return router
