"""Explicit personal display/contact editing with separate optimistic versions."""

import hashlib
import json
import re
from datetime import timedelta

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from .auth import user_view
from .content_models import Media
from .dependencies import database, learner, operation_key
from .errors import DomainError
from .media_api import deliver, save_media
from .models import Consent, MiniSession, User
from .response_contracts import AvatarUpload, AvatarURL, UserProfile
from .security import decrypt, digest, encrypt, lookup
from .transactions import operate


class ProfileChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)
    nickname: str | None = Field(default=None, max_length=80)
    avatar_id: str | None = Field(default=None, max_length=36)


class ContactChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)
    phone: str | None = Field(default=None, max_length=32)
    wechat_contact: str | None = Field(default=None, max_length=64)
    consent_version: str = Field(min_length=1, max_length=64)


def routes():
    router = APIRouter(prefix="/api/mini/v1", tags=["personal profile"])

    @router.patch("/me/profile", response_model=UserProfile)
    def profile(
        body: ProfileChange,
        request: Request,
        user=Depends(learner),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        now, settings = request.app.state.clock(), request.app.state.settings

        def execute():
            if body.version != user.profile_version:
                raise DomainError(409, "profile_changed", "个人资料已变化，请重新获取并核对")
            if "avatar_id" in body.model_fields_set and body.avatar_id:
                avatar = db.get(Media, body.avatar_id)
                if (
                    not avatar
                    or avatar.owner_kind != "mini"
                    or avatar.owner_id != user.id
                    or avatar.kind != "avatar"
                    or avatar.state != "ready"
                ):
                    raise DomainError(422, "avatar_invalid", "请等待头像上传完成，或重新选择图片")
            changed = False
            if "nickname" in body.model_fields_set:
                nickname = (body.nickname or "").strip() or "学习者"
                changed |= nickname != user.nickname
                user.nickname = nickname
            if "avatar_id" in body.model_fields_set:
                changed |= body.avatar_id != user.avatar_id
                user.avatar_id = body.avatar_id
            if changed:
                user.profile_version += 1
                user.profile_updated_at = now
            db.flush()
            return user_view(user, settings)

        return operate(
            db, user, "mini", key, "profile.save", body.model_dump(exclude_unset=True), now, execute
        )

    @router.patch("/me/contact", response_model=UserProfile)
    def contact(
        body: ContactChange,
        request: Request,
        user=Depends(learner),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        now, settings = request.app.state.clock(), request.app.state.settings

        def execute():
            if body.version != user.contact_version:
                raise DomainError(409, "contact_changed", "联系方式已变化，请重新获取并核对")
            changed = []
            values = {
                "phone": (body.phone or "").strip(),
                "wechat_contact": (body.wechat_contact or "").strip(),
            }
            for name, cipher_name in [
                ("phone", "phone_cipher"),
                ("wechat_contact", "wechat_cipher"),
            ]:
                if name not in body.model_fields_set:
                    continue
                old = decrypt(settings, getattr(user, cipher_name)) or ""
                value = values[name]
                if old and not value:
                    raise DomainError(
                        422,
                        "contact_removal_rejected",
                        "已有联系方式不能通过清空删除，请保留或修改",
                        [{"field": name}],
                    )
                if value == old:
                    continue
                if value and name == "phone" and not re.fullmatch(r"1[3-9][0-9]{9}", value):
                    raise DomainError(
                        422, "phone_invalid", "请输入11位大陆手机号", [{"field": name}]
                    )
                if (
                    value
                    and name == "wechat_contact"
                    and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{5,19}", value)
                ):
                    raise DomainError(
                        422,
                        "wechat_contact_invalid",
                        "请填写6–20位微信号，以字母开头",
                        [{"field": name}],
                    )
                changed.append((name, cipher_name, value))
            for name, cipher_name, value in changed:
                prefix = "phone" if name == "phone" else "wechat"
                setattr(user, cipher_name, encrypt(settings, value) if value else None)
                setattr(
                    user,
                    prefix + "_digest",
                    lookup(settings, "contact:" + prefix, value) if value else None,
                )
                setattr(user, prefix + "_source", "user_entered_unverified")
                db.add(
                    Consent(
                        user_id=user.id,
                        purpose="contact." + prefix,
                        version=body.consent_version,
                        accepted_at=now,
                    )
                )
            if changed:
                user.contact_version += 1
                user.contact_updated_at = now
            db.flush()
            return user_view(user, settings)

        return operate(
            db, user, "mini", key, "contact.save", body.model_dump(exclude_unset=True), now, execute
        )

    @router.post("/me/avatar", status_code=201, response_model=AvatarUpload)
    def upload_avatar(
        request: Request,
        file: UploadFile = File(...),
        user=Depends(learner),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        settings, now = request.app.state.settings, request.app.state.clock()
        maximum = settings.image_limit_mb * 1024 * 1024
        data = file.file.read(maximum + 1)
        if not data or len(data) > maximum:
            raise DomainError(413, "upload_limit", "头像为空或超过当前上传限制")

        def execute():
            medium = save_media(db, settings, user, "mini", "avatar", data, now)
            return {"id": medium.id, "state": medium.state}

        return operate(
            db,
            user,
            "mini",
            key,
            "avatar.upload",
            {"sha256": hashlib.sha256(data).hexdigest()},
            now,
            execute,
        )

    @router.get("/me/avatar-url", response_model=AvatarURL)
    def avatar_url(request: Request, user=Depends(learner)):
        if not user.avatar_id:
            return {"url": None}
        expires = request.app.state.clock() + timedelta(minutes=5)
        payload = {
            "purpose": "avatar",
            "media_id": user.avatar_id,
            "session": digest(request.headers["Authorization"].removeprefix("Bearer ")),
            "expires_at": expires.isoformat(),
        }
        credential = encrypt(request.app.state.settings, json.dumps(payload))
        return {"url": "/api/mini/v1/avatar/" + credential}

    @router.head("/avatar/{credential}", include_in_schema=False)
    @router.get("/avatar/{credential}")
    def avatar(
        credential: str, request: Request, db: Session = Depends(database, scope="function")
    ):
        try:
            payload = json.loads(decrypt(request.app.state.settings, credential) or "{}")
        except Exception:
            raise DomainError(401, "resource_expired", "头像地址已失效") from None
        if (
            payload.get("purpose") != "avatar"
            or payload.get("expires_at", "") <= request.app.state.clock().isoformat()
        ):
            raise DomainError(401, "resource_expired", "头像地址已失效")
        session = db.get(MiniSession, payload.get("session", ""))
        if not session or session.expires_at <= request.app.state.clock():
            raise DomainError(401, "login_required", "请主动登录后继续")
        user = db.get(User, session.user_id)
        medium = db.get(Media, payload.get("media_id", ""))
        if (
            not user
            or not medium
            or user.avatar_id != medium.id
            or medium.owner_id != user.id
            or medium.kind != "avatar"
        ):
            raise DomainError(404, "avatar_missing", "头像暂不可用")
        return deliver(medium, request)

    return router
