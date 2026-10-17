"""Each speech URL is bound to its session and rechecks live card/version access."""

import json
from datetime import UTC, timedelta

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from .content_models import Media
from .dependencies import ADMIN_COOKIE, administrator, database, learner, operation_key
from .errors import DomainError
from .media_api import deliver
from .models import AdminSession, MiniSession
from .pronunciation import reference, status
from .pronunciation import request as request_speech
from .pronunciation_models import Pronunciation
from .security import decrypt, digest, encrypt
from .transactions import operate


class SpeechReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version_id: str | None = Field(default=None, max_length=36)
    revision: int | None = Field(default=None, ge=1)


class SpeechState(BaseModel):
    state: str
    job_id: str | None
    error_code: str | None
    url: str | None
    retry_after: int | None


def session_digest(request, role):
    value = (
        request.cookies.get(ADMIN_COOKIE, "")
        if role == "admin"
        else request.headers.get("Authorization", "").removeprefix("Bearer ")
    )
    return digest(value)


def with_grant(value, request, role, actor_id, card_id, word_id, ref, cache_key):
    """Issue a short-lived opaque audio reference without exposing a storage URL."""
    if value["state"] == "ready":
        payload = {
            "role": role,
            "actor": actor_id,
            "session": session_digest(request, role),
            "card_id": card_id,
            "word_id": word_id,
            "version_id": ref.version_id,
            "revision": ref.revision,
            "cache_key": cache_key,
            "expires": int(
                (request.app.state.clock() + timedelta(minutes=5)).replace(tzinfo=UTC).timestamp()
            ),
        }
        credential = encrypt(request.app.state.settings, json.dumps(payload))
        value = {**value, "url": f"/api/{role}/v1/pronunciation/{credential}"}
    return value


def routes(role):
    router = APIRouter(prefix=f"/api/{role}/v1", tags=["controlled word pronunciation"])
    authorize = administrator if role == "admin" else learner

    @router.post("/cards/{card_id}/words/{word_id}/pronunciation", response_model=SpeechState)
    def generate(
        card_id: str,
        word_id: str,
        body: SpeechReference,
        request: Request,
        actor=Depends(authorize),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        settings, now = request.app.state.settings, request.app.state.clock()
        word, reading, config, cache_key = reference(
            db, settings, role, card_id, word_id, body.version_id, body.revision
        )
        value = operate(
            db,
            actor,
            role,
            key,
            "word.pronunciation:" + card_id + ":" + word_id,
            body.model_dump(),
            now,
            lambda: request_speech(
                db, settings, actor, role, word, reading, config, cache_key, now
            ),
        )
        return with_grant(value, request, role, actor.id, card_id, word_id, body, cache_key)

    @router.get("/cards/{card_id}/words/{word_id}/pronunciation", response_model=SpeechState)
    def read(
        card_id: str,
        word_id: str,
        request: Request,
        version_id: str | None = None,
        revision: int | None = None,
        actor=Depends(authorize),
        db: Session = Depends(database, scope="function"),
    ):
        ref = SpeechReference(version_id=version_id, revision=revision)
        _, _, _, cache_key = reference(
            db, request.app.state.settings, role, card_id, word_id, version_id, revision
        )
        return with_grant(
            status(db, cache_key), request, role, actor.id, card_id, word_id, ref, cache_key
        )

    @router.head("/pronunciation/{credential}", include_in_schema=False)
    @router.get("/pronunciation/{credential}")
    def audio(credential: str, request: Request, db: Session = Depends(database, scope="function")):
        settings, now = request.app.state.settings, request.app.state.clock()
        try:
            payload = json.loads(decrypt(settings, credential) or "{}")
        except Exception:
            raise DomainError(401, "speech_grant_invalid", "请重新点击词汇试听") from None
        if (
            not isinstance(payload, dict)
            or payload.get("role") != role
            or payload.get("expires", 0) <= now.replace(tzinfo=UTC).timestamp()
        ):
            raise DomainError(401, "speech_grant_expired", "请重新点击词汇试听")
        session: AdminSession | MiniSession | None
        if role == "admin":
            session = db.get(AdminSession, payload.get("session", ""))
        else:
            session = db.get(MiniSession, payload.get("session", ""))
        actor_id = getattr(session, "admin_id" if role == "admin" else "user_id", None)
        if not session or session.expires_at <= now or actor_id != payload.get("actor"):
            raise DomainError(401, "speech_session_expired", "请重新登录后试听")
        if role == "admin" and payload["session"] != session_digest(request, role):
            raise DomainError(401, "speech_session_expired", "请重新登录后试听")
        _, _, _, cache_key = reference(
            db,
            settings,
            role,
            payload.get("card_id"),
            payload.get("word_id"),
            payload.get("version_id"),
            payload.get("revision"),
        )
        if cache_key != payload.get("cache_key"):
            raise DomainError(409, "pronunciation_changed", "词汇读音已变化，请重新试听")
        cache = db.get(Pronunciation, cache_key)
        if not cache or status(db, cache_key)["state"] != "ready":
            raise DomainError(404, "speech_missing", "发音暂不可用")
        medium = db.get(Media, cache.media_id)
        if not medium or medium.state != "ready":
            raise DomainError(404, "speech_missing", "发音暂不可用")
        return deliver(medium, request)

    return router
