"""Private listening originals and playback, without exposing general administrator media."""

import hashlib
import json
from datetime import UTC, timedelta

from .audio_processing import playback_mp3
from .content_models import Media
from .database import timestamp
from .errors import DomainError
from .media_api import decoded_audio, decoded_image, playback_medium
from .models import MiniSession, identifier
from .security import decrypt, digest, encrypt
from .storage import ObjectStorage


def save_media(db, settings, owner_id, kind, data, name, now):
    limit = (settings.audio_limit_mb if kind == "audio" else settings.image_limit_mb) * 1024 * 1024
    if not data or len(data) > limit:
        raise DomainError(413, "upload_limit", "文件为空或超过当前上传限制")
    storage = ObjectStorage(settings)
    media_id = identifier()
    checksum = hashlib.sha256(data).hexdigest()
    key = f"{settings.environment}/media/{media_id}/{checksum}"
    values = {
        "id": media_id,
        "owner_kind": "listening",
        "owner_id": owner_id,
        "kind": kind,
        "state": "ready",
        "sha256": checksum,
        "size": len(data),
        "storage_key": key,
        "created_at": now,
    }
    derivatives = []
    if kind == "audio":
        expected = {
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".m4a": "audio/mp4",
            ".aac": "audio/aac",
        }
        from pathlib import PurePosixPath

        extension = PurePosixPath(name).suffix.lower()
        if extension not in expected:
            raise DomainError(422, "audio_format_unsupported", "仅支持MP3、M4A、WAV、AAC")
        content_type, duration = decoded_audio(data)
        if expected[extension] != content_type:
            raise DomainError(422, "audio_format_mismatch", "文件后缀与实际音频格式不符")
        output = playback_mp3(data, content_type, duration, limit)
        playback_id = media_id if content_type == "audio/mpeg" else identifier()
        values.update(
            content_type=content_type,
            duration=duration,
            playback_id=playback_id,
            processing_stage="ready",
        )
        if playback_id != media_id:
            output_hash = hashlib.sha256(output).hexdigest()
            playback_key = f"{settings.environment}/media/{playback_id}/{output_hash}"
            storage.put(playback_key, output, "audio/mpeg")
            derivatives.append(
                Media(
                    id=playback_id,
                    owner_kind="listening",
                    owner_id=owner_id,
                    kind="audio_playback",
                    state="ready",
                    content_type="audio/mpeg",
                    duration=duration,
                    sha256=output_hash,
                    size=len(output),
                    storage_key=playback_key,
                    created_at=now,
                )
            )
    else:
        content_type, width, height, thumb_data, dimensions = decoded_image(data)
        thumb_id = identifier()
        thumb_hash = hashlib.sha256(thumb_data).hexdigest()
        thumb_key = f"{settings.environment}/media/{thumb_id}/{thumb_hash}"
        storage.put(thumb_key, thumb_data, "image/webp")
        values.update(content_type=content_type, width=width, height=height, thumbnail_id=thumb_id)
        derivatives.append(
            Media(
                id=thumb_id,
                owner_kind="listening",
                owner_id=owner_id,
                kind="thumbnail",
                state="ready",
                content_type="image/webp",
                width=dimensions[0],
                height=dimensions[1],
                sha256=thumb_hash,
                size=len(thumb_data),
                storage_key=thumb_key,
                created_at=now,
            )
        )
    storage.put(key, data, values["content_type"])
    row = Media(**values)
    db.add_all([row, *derivatives])
    db.flush()
    return row


def view(row):
    return {
        "id": row.id,
        "kind": row.kind,
        "state": row.state,
        "duration": row.duration,
        "thumbnail_id": row.thumbnail_id,
        "playback_id": row.playback_id,
        "content_type": row.content_type,
        "size": row.size,
        "width": row.width,
        "height": row.height,
    }


def controlled_media(db, payload, media_id, *, thumbnail=False):
    ids = [payload.get("audio_id"), payload.get("image_id")]
    if thumbnail:
        image = db.get(Media, payload.get("image_id")) if payload.get("image_id") else None
        row = db.get(Media, image.thumbnail_id) if image and image.thumbnail_id else None
    else:
        row = db.get(Media, media_id) if media_id in ids else None
    if not row or row.state != "ready" or row.owner_kind != "listening":
        raise DomainError(404, "listening_media_missing", "素材暂不可用")
    return playback_medium(db, row)


def issue_ticket(request, user_id, article_id, version_id, media_id, *, purpose="content"):
    now = request.app.state.clock()
    expires = now + timedelta(minutes=5)
    bearer = request.headers.get("Authorization", "").removeprefix("Bearer ")
    credential = encrypt(
        request.app.state.settings,
        json.dumps(
            {
                "purpose": "listening:" + purpose,
                "user_id": user_id,
                "session": digest(bearer),
                "article_id": article_id,
                "version_id": version_id,
                "media_id": media_id,
                "expires": expires.replace(tzinfo=UTC).timestamp(),
            }
        ),
    )
    return {"url": "/api/mini/v1/listening/media/" + credential, "expires_at": timestamp(expires)}


def read_ticket(db, request, credential):
    now = request.app.state.clock()
    try:
        data = json.loads(decrypt(request.app.state.settings, credential) or "{}")
        if (
            data["purpose"] not in {"listening:content", "listening:thumbnail", "listening:speech"}
            or data["expires"] <= now.replace(tzinfo=UTC).timestamp()
        ):
            raise ValueError("invalid grant")
        session = db.get(MiniSession, data["session"])
        if not session or session.expires_at <= now or session.user_id != data["user_id"]:
            raise ValueError("invalid session")
        bearer = request.headers.get("Authorization")
        if bearer and digest(bearer.removeprefix("Bearer ")) != data["session"]:
            raise ValueError("different session")
    except Exception:
        raise DomainError(401, "listening_media_ticket_invalid", "请重新获取资源") from None
    return data
