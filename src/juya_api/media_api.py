"""Decode actual uploads and authorize every image/audio request, including ranges."""

import hashlib
import io
import json
import re
import shutil
import subprocess
import tempfile
import warnings
import wave
from datetime import timedelta
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from .content_models import Media, MediaTicket
from .content_service import published_card
from .database import timestamp
from .dependencies import administrator, database, learner, operation_key
from .errors import DomainError
from .models import MiniSession, identifier
from .security import digest, token
from .storage import ObjectStorage
from .transactions import operate


def media_view(medium: Media) -> dict:
    """Return safe media metadata and controlled identifiers, never OSS object credentials."""
    return {
        "id": medium.id,
        "kind": medium.kind,
        "state": medium.state,
        "content_type": medium.content_type,
        "size": medium.size,
        "width": medium.width,
        "height": medium.height,
        "duration": medium.duration,
        "thumbnail_id": medium.thumbnail_id,
    }


def decoded_image(data: bytes):
    """Reject fake types, animated images and decompression bombs before thumbnailing."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as original:
                if (
                    original.format not in {"PNG", "JPEG", "WEBP"}
                    or getattr(original, "n_frames", 1) != 1
                ):
                    raise ValueError("static PNG/JPEG/WebP required")
                if original.width * original.height > 20_000_000:
                    raise ValueError("image dimensions exceed processing budget")
                content_type = Image.MIME[original.format]
                original.verify()
            with Image.open(io.BytesIO(data)) as original:
                oriented = ImageOps.exif_transpose(original)
                width, height = oriented.size
                thumbnail = oriented.convert("RGB")
                thumbnail.thumbnail((780, 780))
                output = io.BytesIO()
                thumbnail.save(output, "WEBP", quality=85)
                return content_type, width, height, output.getvalue(), thumbnail.size
    except (
        ValueError,
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise DomainError(
            422, "image_invalid", "图片无法读取，请选择静态 PNG、JPEG 或 WebP 图片"
        ) from None


def decoded_audio(data: bytes):
    """Read real PCM WAV or use bounded FFprobe decoding for supported whole audio files."""
    try:
        with wave.open(io.BytesIO(data), "rb") as recording:
            duration = recording.getnframes() / recording.getframerate()
            if duration <= 0 or recording.getnchannels() not in {1, 2}:
                raise ValueError("empty or unsupported recording")
            return "audio/wav", duration
    except (wave.Error, EOFError, ValueError):
        pass
    executable = shutil.which("ffprobe")
    if not executable:
        raise DomainError(
            422, "audio_decoder_unavailable", "音频暂时无法解码，请稍后重试或选择有效的 WAV 文件"
        )
    try:
        with tempfile.TemporaryDirectory(prefix="juya-audio-") as directory:
            path = Path(directory) / "input"
            path.write_bytes(data)
            result = subprocess.run(
                [
                    executable,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration,format_name:stream=codec_type",
                    "-of",
                    "json",
                    str(path),
                ],
                capture_output=True,
                timeout=30,
                check=True,
            )
            info = json.loads(result.stdout)
            if not any(s.get("codec_type") == "audio" for s in info.get("streams", [])):
                raise ValueError("no audio stream")
            duration = float(info["format"]["duration"])
            if duration <= 0:
                raise ValueError("invalid duration")
            name = info["format"]["format_name"]
            if "mp3" in name:
                return "audio/mpeg", duration
            if "mov" in name or "m4a" in name:
                return "audio/mp4", duration
            if "aac" in name:
                return "audio/aac", duration
            raise ValueError("unsupported audio container")
    except (ValueError, KeyError, subprocess.SubprocessError):
        raise DomainError(422, "audio_invalid", "音频无法读取，请更换完整音频文件") from None


def save_media(db, settings, actor, role: str, kind: str, data: bytes, now) -> Media:
    """Persist decoded immutable originals and derived thumbnails as one database unit."""
    storage = ObjectStorage(settings)
    width = height = duration = None
    thumbnail_data = thumbnail_size = None
    if kind in {"image", "avatar"}:
        content_type, width, height, thumbnail_data, thumbnail_size = decoded_image(data)
    else:
        content_type, duration = decoded_audio(data)
    media_id = identifier()
    checksum = hashlib.sha256(data).hexdigest()
    storage_key = f"{settings.environment}/media/{media_id}/{checksum}"
    storage.put(storage_key, data, content_type)
    medium = Media(
        id=media_id,
        owner_kind=role,
        owner_id=actor.id,
        kind=kind,
        storage_key=storage_key,
        content_type=content_type,
        size=len(data),
        sha256=checksum,
        width=width,
        height=height,
        duration=duration,
        created_at=now,
    )
    if thumbnail_data is not None:
        assert thumbnail_size is not None
        thumb_id = identifier()
        thumb_hash = hashlib.sha256(thumbnail_data).hexdigest()
        thumb_key = f"{settings.environment}/media/{thumb_id}/{thumb_hash}"
        storage.put(thumb_key, thumbnail_data, "image/webp")
        thumbnail = Media(
            id=thumb_id,
            owner_kind=role,
            owner_id=actor.id,
            kind="thumbnail",
            storage_key=thumb_key,
            content_type="image/webp",
            size=len(thumbnail_data),
            sha256=thumb_hash,
            width=thumbnail_size[0],
            height=thumbnail_size[1],
            created_at=now,
        )
        db.add(thumbnail)
        medium.thumbnail_id = thumb_id
    db.add(medium)
    db.flush()
    return medium


def deliver(medium: Media, request: Request):
    """Support native audio seeking while protecting metadata and all range requests."""
    size = medium.size
    start, end, status = 0, size - 1, 200
    headers = {
        "Cache-Control": "no-store",
        "Accept-Ranges": "bytes",
        "X-Content-Type-Options": "nosniff",
    }
    value = request.headers.get("range")
    if value:
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", value)
        if not match or not any(match.groups()):
            return Response(
                status_code=416, headers={**headers, "Content-Range": f"bytes */{size}"}
            )
        if match[1]:
            start = int(match[1])
            end = min(int(match[2]), size - 1) if match[2] else size - 1
        else:
            start = max(0, size - int(match[2]))
        if start > end or start >= size:
            return Response(
                status_code=416, headers={**headers, "Content-Range": f"bytes */{size}"}
            )
        status = 206
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    headers["Content-Length"] = str(end - start + 1)
    storage = ObjectStorage(request.app.state.settings)
    if request.method == "HEAD":
        stream = storage.stream(medium.storage_key, 0, 0)
        next(stream, None)
        stream.close()
        return Response(status_code=status, headers=headers, media_type=medium.content_type)
    return StreamingResponse(
        storage.stream(medium.storage_key, start, end),
        status_code=status,
        headers=headers,
        media_type=medium.content_type,
    )


def admin_routes():
    router = APIRouter(prefix="/api/admin/v1", tags=["private administrator media"])

    @router.post("/media", status_code=201)
    def upload(
        request: Request,
        kind: Literal["image", "audio"],
        file: UploadFile = File(...),
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database),
    ):
        settings, now = request.app.state.settings, request.app.state.clock()
        limit = (
            (settings.image_limit_mb if kind == "image" else settings.audio_limit_mb) * 1024 * 1024
        )
        data = file.file.read(limit + 1)
        if not data or len(data) > limit:
            raise DomainError(413, "upload_limit", "文件为空或超过当前上传限制")
        return operate(
            db,
            admin,
            "admin",
            key,
            "media.upload",
            {"kind": kind, "sha256": hashlib.sha256(data).hexdigest()},
            now,
            lambda: media_view(save_media(db, settings, admin, "admin", kind, data, now)),
        )

    @router.api_route("/media/{media_id}", methods=["GET", "HEAD"])
    def read(
        media_id: str,
        request: Request,
        admin=Depends(administrator),
        db: Session = Depends(database),
    ):
        medium = db.get(Media, media_id)
        if not medium or medium.state != "ready":
            raise DomainError(404, "media_missing", "素材不可用")
        return deliver(medium, request)

    @router.get("/media/{media_id}/status")
    def status(media_id: str, admin=Depends(administrator), db: Session = Depends(database)):
        medium = db.get(Media, media_id)
        if not medium:
            raise DomainError(404, "media_missing", "素材不可用")
        return media_view(medium)

    return router


def mini_routes():
    router = APIRouter(prefix="/api/mini/v1", tags=["controlled published resources"])

    @router.get("/cards/{card_id}/media/{media_id}/url")
    def issue(
        card_id: str,
        media_id: str,
        version_id: str,
        request: Request,
        user=Depends(learner),
        db: Session = Depends(database),
    ):
        _, version = published_card(db, card_id, version_id)
        medium = db.get(Media, media_id)
        image = db.get(Media, version.payload["image_id"])
        allowed = {
            version.payload["image_id"],
            version.payload["audio_id"],
            image.thumbnail_id if image else None,
        }
        if not medium or medium.id not in allowed or medium.state != "ready":
            raise DomainError(404, "media_missing", "素材不可用")
        credential = token("med_")
        expires = request.app.state.clock() + timedelta(minutes=5)
        db.add(
            MediaTicket(
                token_digest=digest(credential),
                session_digest=digest(request.headers["Authorization"].removeprefix("Bearer ")),
                user_id=user.id,
                card_id=card_id,
                version_id=version.id,
                media_id=medium.id,
                expires_at=expires,
            )
        )
        return {"url": "/api/mini/v1/media/" + credential, "expires_at": timestamp(expires)}

    @router.api_route("/media/{credential}", methods=["GET", "HEAD"])
    def read(credential: str, request: Request, db: Session = Depends(database)):
        now = request.app.state.clock()
        ticket = db.get(MediaTicket, digest(credential))
        if not ticket or ticket.expires_at <= now:
            raise DomainError(401, "resource_expired", "资源地址已失效，请重新获取")
        session = db.get(MiniSession, ticket.session_digest)
        if not session or session.expires_at <= now or session.user_id != ticket.user_id:
            raise DomainError(401, "login_required", "请主动登录后继续")
        published_card(db, ticket.card_id, ticket.version_id)
        medium = db.get(Media, ticket.media_id)
        if not medium or medium.state != "ready":
            raise DomainError(404, "media_missing", "素材不可用")
        return deliver(medium, request)

    return router
