"""Lookup and speech for exact published body tokens, with session-bound audio grants."""

import json
from datetime import UTC, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from .content_models import Media
from .dependencies import database, learner, operation_key
from .dictionary import DictionaryReference, DictionaryResult, controlled_target, lookup
from .errors import DomainError
from .media_api import deliver
from .models import MiniSession
from .pronunciation import request as request_speech
from .pronunciation import status
from .pronunciation_api import SpeechState, session_digest
from .pronunciation_models import Pronunciation
from .security import decrypt, encrypt
from .transactions import operate


def with_grant(value, request, user_id, card_id, ref, cache_key):
    """Keep native audio usable without a public storage URL or learner credential in a URL."""
    if value["state"] != "ready":
        return value
    payload = {
        "purpose": "dictionary-speech",
        "actor": user_id,
        "session": session_digest(request, "mini"),
        "card_id": card_id,
        "reference": ref.model_dump(),
        "cache_key": cache_key,
        "expires": int(
            (request.app.state.clock() + timedelta(minutes=5)).replace(tzinfo=UTC).timestamp()
        ),
    }
    credential = encrypt(request.app.state.settings, json.dumps(payload))
    return {**value, "url": "/api/mini/v1/dictionary-pronunciation/" + credential}


def routes():
    router = APIRouter(prefix="/api/mini/v1", tags=["controlled body dictionary"])

    @router.get("/cards/{card_id}/dictionary", response_model=DictionaryResult)
    def dictionary(
        card_id: str,
        ref: Annotated[DictionaryReference, Query()],
        request: Request,
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        target = controlled_target(db, request.app.state.settings, card_id, ref)
        return lookup(target, request.app.state.dictionary)

    @router.post("/cards/{card_id}/dictionary/pronunciation", response_model=SpeechState)
    def generate(
        card_id: str,
        body: DictionaryReference,
        request: Request,
        user=Depends(learner),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        settings, now = request.app.state.settings, request.app.state.clock()
        target = controlled_target(db, settings, card_id, body)
        if not target.reading:
            raise DomainError(422, "pronunciation_unconfirmed", "当前单词发音暂不可用")
        value = operate(
            db,
            user,
            "mini",
            key,
            "dictionary.pronunciation:" + card_id,
            body.model_dump(),
            now,
            lambda: request_speech(
                db,
                settings,
                user,
                "mini",
                {"english": target.word},
                target.reading,
                target.config,
                target.cache_key,
                now,
            ),
        )
        return with_grant(value, request, user.id, card_id, body, target.cache_key)

    @router.get("/cards/{card_id}/dictionary/pronunciation", response_model=SpeechState)
    def read(
        card_id: str,
        ref: Annotated[DictionaryReference, Query()],
        request: Request,
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        target = controlled_target(db, request.app.state.settings, card_id, ref)
        if not target.reading:
            raise DomainError(422, "pronunciation_unconfirmed", "当前单词发音暂不可用")
        return with_grant(
            status(db, target.cache_key), request, user.id, card_id, ref, target.cache_key
        )

    @router.head("/dictionary-pronunciation/{credential}", include_in_schema=False)
    @router.get("/dictionary-pronunciation/{credential}")
    def audio(credential: str, request: Request, db: Session = Depends(database, scope="function")):
        settings, now = request.app.state.settings, request.app.state.clock()
        try:
            payload = json.loads(decrypt(settings, credential) or "{}")
            if not isinstance(payload, dict) or payload.get("purpose") != "dictionary-speech":
                raise ValueError("wrong purpose")
            card_id = payload.get("card_id")
            if not isinstance(card_id, str) or not 1 <= len(card_id) <= 36:
                raise ValueError("invalid card reference")
            ref = DictionaryReference.model_validate(payload.get("reference"))
            expires = payload.get("expires", 0)
            if not isinstance(expires, int) or expires <= now.replace(tzinfo=UTC).timestamp():
                raise ValueError("expired")
        except (ValueError, TypeError, ValidationError):
            raise DomainError(401, "speech_grant_invalid", "请重新点击单词试听") from None
        except Exception:
            raise DomainError(401, "speech_grant_invalid", "请重新点击单词试听") from None
        session = db.get(MiniSession, payload.get("session", ""))
        if (
            not session
            or session.expires_at <= now
            or session.user_id != payload.get("actor")
            or (
                request.headers.get("Authorization")
                and payload["session"] != session_digest(request, "mini")
            )
        ):
            raise DomainError(401, "speech_session_expired", "请重新登录后试听")
        target = controlled_target(db, settings, card_id, ref)
        if not target.reading or target.cache_key != payload.get("cache_key"):
            raise DomainError(409, "pronunciation_changed", "单词读音已变化，请重新试听")
        cache = db.get(Pronunciation, target.cache_key)
        medium = db.get(Media, cache.media_id) if cache and cache.media_id else None
        if (
            status(db, target.cache_key)["state"] != "ready"
            or not medium
            or medium.state != "ready"
            or medium.kind != "pronunciation"
        ):
            raise DomainError(404, "speech_missing", "发音暂不可用")
        return deliver(medium, request)

    return router
