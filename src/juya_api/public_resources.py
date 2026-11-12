"""Anonymous grants are sealed, purpose-limited and revalidated on every delivery.

These stateless grants never share the private MediaTicket format or its user/session
constraints. Removing a free flag, publication or current version revokes delivery.
"""

import json
import math
from datetime import UTC, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .access_service import require_access
from .content_models import Media
from .content_service import published_card
from .database import timestamp
from .dependencies import database
from .errors import DomainError
from .media_api import deliver, deliver_thumbnail, playback_medium
from .media_permissions import require_public_image
from .security import decrypt, encrypt

PREFIX = "pub1_"
PURPOSES = {
    "scene:content",
    "scene:summary",
    "scene:study_note",
    "scene:word",
    "listening:content",
    "listening:summary",
    "listening:word",
}


def issue(
    request,
    domain,
    identifier,
    version_id,
    purpose,
    *,
    media_id=None,
    note_version_id=None,
    word_id=None,
    cache_key=None,
):
    """Seal one current server-resolved reference for exactly five minutes."""
    expires = request.app.state.clock() + timedelta(seconds=300)
    purpose = domain + ":" + purpose
    if purpose not in PURPOSES:
        raise ValueError("Unsupported public resource purpose")
    payload = {
        "format": "juya-public-resource-v1",
        "purpose": purpose,
        "id": identifier,
        "version_id": version_id,
        "media_id": media_id,
        "note_version_id": note_version_id,
        "word_id": word_id,
        "cache_key": cache_key,
        "expires": expires.replace(tzinfo=UTC).timestamp(),
    }
    credential = PREFIX + encrypt(request.app.state.settings, json.dumps(payload))
    return {"url": "/api/mini/v1/public/resources/" + credential, "expires_at": timestamp(expires)}


def read(request, credential):
    """Reject other grant formats, unknown purposes and malformed/expired references."""
    try:
        if not credential.startswith(PREFIX):
            raise ValueError("Not public")
        data = json.loads(decrypt(request.app.state.settings, credential[len(PREFIX) :]) or "{}")
        if (
            not isinstance(data, dict)
            or data.get("format") != "juya-public-resource-v1"
            or data.get("purpose") not in PURPOSES
            or not isinstance(data.get("expires"), (int, float))
            or not math.isfinite(data["expires"])
            or data["expires"] <= request.app.state.clock().replace(tzinfo=UTC).timestamp()
            or any(not isinstance(data.get(k), str) or not data[k] for k in ("id", "version_id"))
        ):
            raise ValueError("Invalid public grant")
        if set(data) != {
            "format",
            "purpose",
            "id",
            "version_id",
            "media_id",
            "note_version_id",
            "word_id",
            "cache_key",
            "expires",
        }:
            raise ValueError("Invalid public fields")
        required = ["word_id", "cache_key"] if data["purpose"].endswith(":word") else ["media_id"]
        if data["purpose"] == "scene:study_note":
            required.append("note_version_id")
        if any(not isinstance(data.get(k), str) or not data[k] for k in required):
            raise ValueError("Invalid public reference")
    except Exception:
        raise DomainError(401, "public_resource_expired", "资源地址已失效，请重新获取") from None
    return data


def scene_medium(db, request, card_id, version_id, media_id, purpose, note_version_id=None):
    """Resolve only the live thumbnail or current free scene media/note."""
    card, version = published_card(db, card_id, version_id)
    image = db.get(Media, version.payload["image_id"])
    if purpose == "summary":
        allowed = {image.thumbnail_id} if image and image.thumbnail_id else set()
    else:
        require_access(db, None, card_id, request.app.state.clock())
        if purpose == "study_note":
            from .study_notes import require_note

            require_note(db, card, media_id, note_version_id)
            allowed = {media_id}
        elif purpose == "content":
            allowed = {version.payload["image_id"], version.payload["audio_id"]}
            if image and image.thumbnail_id:
                allowed.add(image.thumbnail_id)
        else:
            raise DomainError(404, "media_missing", "素材不可用")
    medium = db.get(Media, media_id) if media_id in allowed else None
    if not medium or medium.state != "ready":
        raise DomainError(404, "media_missing", "素材不可用")
    return playback_medium(db, medium)


def routes():
    router = APIRouter(prefix="/api/mini/v1/public/resources", tags=["public controlled resources"])

    @router.head("/{credential}", include_in_schema=False)
    @router.get("/{credential}")
    def resource(
        credential: str,
        request: Request,
        thumbnail: Literal["list"] | None = None,
        db: Session = Depends(database, scope="function"),
    ):
        data = read(request, credential)
        domain, purpose = data["purpose"].split(":")
        if purpose in {"word", "study_note"}:
            raise DomainError(401, "public_resource_expired", "资源地址已失效，请重新获取")
        referenced = db.get(Media, data["media_id"])
        if referenced is not None:
            require_public_image(referenced)
        if domain == "scene":
            medium = scene_medium(
                db,
                request,
                data["id"],
                data["version_id"],
                data["media_id"],
                purpose,
                data.get("note_version_id"),
            )
        else:
            from . import listening_media, listening_service

            if purpose == "summary":
                version = listening_service.thumbnail_version(db, data["id"], data["version_id"])
            else:
                _, version = listening_service.published(
                    db, None, data["id"], request.app.state.clock(), data["version_id"]
                )
            medium = listening_media.controlled_media(
                db, version.payload, data["media_id"], thumbnail=purpose == "summary"
            )
        require_public_image(medium)
        if (domain == "listening" and purpose == "summary") or thumbnail is not None:
            return deliver_thumbnail(medium, request)
        return deliver(medium, request)

    return router
