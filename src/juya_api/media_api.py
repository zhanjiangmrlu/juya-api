"""Decode actual uploads and authorize every image/audio request, including ranges."""

import hashlib
import io
import json
import math
import re
import shutil
import subprocess
import tempfile
import warnings
import wave
from datetime import timedelta
from pathlib import Path, PurePosixPath
from typing import Literal

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from .content_models import Media, MediaTicket
from .content_service import published_card
from .database import timestamp
from .dependencies import administrator, database, learner, operation_key, write_transaction
from .errors import DomainError
from .job_models import Job
from .jobs import enqueue
from .media_permissions import summary_thumbnail
from .models import MiniSession, identifier
from .response_contracts import MediaMetadata, ResourceURL, UploadConfiguration
from .security import digest, token
from .storage import ObjectStorage
from .transactions import operate
from .zip_names import import_file_name


def media_view(medium: Media, db=None) -> dict:
    """Return safe media metadata and controlled identifiers, never OSS object credentials."""
    job = db.get(Job, medium.job_id) if db is not None and medium.job_id else None
    failed = job is not None and job.state == "failed"
    preparing_legacy = (
        medium.kind == "audio"
        and medium.state == "ready"
        and not medium.playback_id
        and job is not None
        and job.state not in {"succeeded", "failed"}
    )
    original_name = None
    if db is not None and medium.owner_kind == "admin":
        from sqlalchemy import select

        from .admin_action_models import AdminMediaSource
        from .import_models import ImportFile

        source = db.get(AdminMediaSource, medium.id)
        if source:
            original_name = source.original_name
        else:
            imported_file = db.scalar(
                select(ImportFile).where(ImportFile.media_id == medium.id).limit(1)
            )
            original_name = import_file_name(db, imported_file) if imported_file else None
    playback = db.get(Media, medium.playback_id) if db is not None and medium.playback_id else None
    return {
        "playback_id": medium.playback_id,
        "playback_content_type": playback.content_type if playback else None,
        "processing_stage": "failed" if failed else medium.processing_stage,
        "original_name": original_name,
        "job_id": medium.job_id,
        "error_code": job.error_code if failed and job else None,
        "error": (
            {
                "audio_invalid": "音频格式无效、受保护或内容不完整，请更换可解码的完整文件",
                "audio_format_mismatch": "音频真实格式与后缀不一致，请上传原始格式文件",
                "audio_conversion_failed": "MP3兼容处理未通过完整性校验，请重试或更换文件",
                "audio_conversion_unavailable": "音频转换暂不可用，请稍后重试",
                "audio_decoder_unavailable": "音频校验服务暂不可用，请稍后重试",
            }.get(job.error_code, "素材处理失败，请重试或重新上传")
            if failed and job
            else None
        ),
        "id": medium.id,
        "kind": medium.kind,
        "state": "failed" if failed else "processing" if preparing_legacy else medium.state,
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


def bounded_wave_input(data: bytes) -> bytes:
    """Resolve a streamed WAV's explicit unknown lengths from its bounded upload bytes."""
    if data[:4] != b"RIFF" or data[4:8] != b"\xff" * 4 or data[8:12] != b"WAVE":
        return data
    offset = 12
    while offset + 8 <= len(data):
        size = int.from_bytes(data[offset + 4 : offset + 8], "little")
        if data[offset : offset + 4] == b"data" and size == 0xFFFFFFFF:
            resolved = bytearray(data)
            resolved[4:8] = (len(data) - 8).to_bytes(4, "little")
            resolved[offset + 4 : offset + 8] = (len(data) - offset - 8).to_bytes(4, "little")
            return bytes(resolved)
        offset += 8 + size + (size & 1)
    return data


def decoded_audio(data: bytes):
    """Verify complete PCM frames or fully decode a bounded, explicitly allowed demuxer."""
    try:
        with wave.open(io.BytesIO(bounded_wave_input(data)), "rb") as recording:
            rate, channels, frames, width = (
                recording.getframerate(),
                recording.getnchannels(),
                recording.getnframes(),
                recording.getsampwidth(),
            )
            if rate <= 0 or channels not in {1, 2} or width not in {1, 2, 3, 4} or frames <= 0:
                raise DomainError(422, "audio_invalid", "音频帧或格式无效，请更换完整音频")
            expected = frames * channels * width
            if expected > len(data):
                raise DomainError(422, "audio_invalid", "音频不完整，请重新上传原始文件")
            received = 0
            while block := recording.readframes(65536):
                received += len(block)
            if received != expected:
                raise DomainError(422, "audio_invalid", "音频不完整，请重新上传原始文件")
            duration = frames / rate
            return "audio/wav", duration
    except (wave.Error, EOFError, ValueError):
        pass
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        demuxer = "wav"
    elif len(data) >= 12 and data[4:8] == b"ftyp":
        demuxer = "mov"
    elif len(data) >= 2 and data[0] == 255 and data[1] & 0xF6 == 0xF0:
        demuxer = "aac"
    elif data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 255 and data[1] & 0xE0 == 0xE0):
        demuxer = "mp3"
    else:
        raise DomainError(422, "audio_invalid", "音频真实格式不支持，请选择MP3、M4A、WAV或AAC")
    executable, decoder = shutil.which("ffprobe"), shutil.which("ffmpeg")
    if not executable or not decoder:
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
                    "-protocol_whitelist",
                    "file,pipe",
                    "-f",
                    demuxer,
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
            streams = info.get("streams", [])
            if not any(s.get("codec_type") == "audio" for s in streams) or any(
                s.get("codec_type") == "video" for s in streams
            ):
                raise ValueError("no audio stream")
            decoded = subprocess.run(
                [
                    decoder,
                    "-nostdin",
                    "-v",
                    "error",
                    "-xerror",
                    "-err_detect",
                    "explode",
                    "-threads",
                    "1",
                    "-protocol_whitelist",
                    "file,pipe",
                    "-f",
                    demuxer,
                    "-i",
                    str(path),
                    "-map",
                    "0:a:0",
                    "-vn",
                    "-sn",
                    "-dn",
                    "-progress",
                    "pipe:1",
                    "-nostats",
                    "-f",
                    "null",
                    "-",
                ],
                capture_output=True,
                timeout=60,
                check=True,
            )
            # ADTS/VBR container duration is an estimate; use completed decode timestamps.
            times = [
                int(line.split("=", 1)[1])
                for line in decoded.stdout.decode("ascii").splitlines()
                if line.startswith("out_time_us=")
            ]
            duration = max(times, default=0) / 1_000_000
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError("invalid decoded duration")
            name = info["format"]["format_name"]
            if name == "wav":
                return "audio/wav", duration
            if "mp3" in name:
                return "audio/mpeg", duration
            if "mov" in name or "m4a" in name:
                return "audio/mp4", duration
            if "aac" in name:
                return "audio/aac", duration
            raise ValueError("unsupported audio container")
    except (ValueError, KeyError, subprocess.SubprocessError):
        raise DomainError(422, "audio_invalid", "音频无法读取，请更换完整音频文件") from None


def save_media(
    db, settings, actor, role: str, kind: str, data: bytes, now, *, original_name=None
) -> Media:
    """Persist decoded immutable originals and derived thumbnails as one database unit."""
    if (
        kind == "audio"
        and original_name
        and PurePosixPath(original_name).suffix.lower() not in {".mp3", ".m4a", ".wav", ".aac"}
    ):
        raise DomainError(422, "audio_format_unsupported", "仅支持 MP3、M4A、WAV、AAC 完整音频")
    storage = ObjectStorage(settings)
    media_id = identifier()
    checksum = hashlib.sha256(data).hexdigest()
    storage_key = f"{settings.environment}/media/{media_id}/{checksum}"
    storage.put(storage_key, data, "application/octet-stream")
    medium = Media(
        id=media_id,
        owner_kind=role,
        owner_id=actor.id,
        kind=kind,
        state="processing",
        processing_stage="validating",
        storage_key=storage_key,
        content_type="application/octet-stream",
        size=len(data),
        sha256=checksum,
        created_at=now,
    )
    db.add(medium)
    job = enqueue(
        db, "media.decode", role, actor.id, {"media_id": media_id}, now, settings=settings
    )
    medium.job_id = job.id
    db.flush()
    if role == "admin" and original_name:
        from .admin_action_models import AdminMediaSource

        db.add(AdminMediaSource(media_id=medium.id, original_name=original_name))
        db.flush()
    return medium


def retry_media(db, settings, actor, role, media_id, key, now):
    """Retry a known transient processing failure while retaining the original upload."""

    def execute():
        medium = db.get(Media, media_id)
        if not medium or medium.owner_kind != role or medium.owner_id != actor.id:
            raise DomainError(404, "media_missing", "素材不可用")
        previous = db.get(Job, medium.job_id) if medium.job_id else None
        legacy = medium.kind == "audio" and medium.state == "ready" and not medium.playback_id
        if previous and previous.state not in {"succeeded", "failed"}:
            return media_view(medium, db)
        if not legacy and (not previous or previous.state != "failed"):
            return media_view(medium, db)
        if previous and previous.error_code in {
            "image_invalid",
            "audio_invalid",
            "media_invalid",
            "audio_format_mismatch",
            "audio_format_unsupported",
        }:
            raise DomainError(422, "media_invalid", "素材无法读取，请重新选择文件")
        job = enqueue(
            db, "media.decode", role, actor.id, {"media_id": medium.id}, now, settings=settings
        )
        medium.job_id = job.id
        # Published legacy references remain readable while their derivative is prepared.
        if not legacy:
            medium.state = "processing"
        medium.processing_stage = "validating" if legacy else medium.processing_stage
        db.flush()
        return media_view(medium, db)

    return operate(db, actor, role, key, "media.retry:" + media_id, {}, now, execute)


def playback_medium(db, medium: Media) -> Media:
    """Resolve playback only after the caller authorized the original logical reference."""
    if medium.kind != "audio" or not medium.playback_id or medium.playback_id == medium.id:
        return medium
    playback = db.get(Media, medium.playback_id)
    if (
        not playback
        or playback.state != "ready"
        or playback.kind != "audio_playback"
        or playback.owner_kind != medium.owner_kind
        or playback.owner_id != medium.owner_id
    ):
        raise DomainError(503, "audio_playback_unavailable", "播放资源暂不可用，请稍后重试")
    return playback


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

    @router.post("/media", status_code=201, response_model=MediaMetadata)
    def upload(
        request: Request,
        kind: Literal["image", "audio"],
        file: UploadFile = File(...),
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        settings, now = request.app.state.settings, request.app.state.clock()
        limit = (
            (settings.image_limit_mb if kind == "image" else settings.audio_limit_mb) * 1024 * 1024
        )
        data = file.file.read(limit + 1)
        if not data or len(data) > limit:
            raise DomainError(413, "upload_limit", "文件为空或超过当前上传限制")
        name = PurePosixPath((file.filename or "").replace("\\", "/")).name
        if not name or len(name) > 255 or any(ord(c) < 32 for c in name):
            raise DomainError(422, "upload_filename", "文件名不可用，请重命名后上传")
        return operate(
            db,
            admin,
            "admin",
            key,
            "media.upload",
            {"kind": kind, "sha256": hashlib.sha256(data).hexdigest()},
            now,
            lambda: media_view(
                save_media(db, settings, admin, "admin", kind, data, now, original_name=name), db
            ),
        )

    @router.post("/media/{media_id}/retry", response_model=MediaMetadata)
    def retry(
        media_id: str,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        return retry_media(
            db, request.app.state.settings, admin, "admin", media_id, key, request.app.state.clock()
        )

    @router.get("/media/configuration", response_model=UploadConfiguration)
    def configuration(request: Request, admin=Depends(administrator)):
        settings = request.app.state.settings
        return {
            "image_limit_bytes": settings.image_limit_mb * 1024 * 1024,
            "audio_limit_bytes": settings.audio_limit_mb * 1024 * 1024,
            "archive_limit_bytes": settings.archive_limit_mb * 1024 * 1024,
            "import_card_limit": settings.import_card_limit,
        }

    @router.head("/media/{media_id}", include_in_schema=False)
    @router.get("/media/{media_id}")
    def read(
        media_id: str,
        request: Request,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        medium = db.get(Media, media_id)
        if not medium or medium.state != "ready":
            raise DomainError(404, "media_missing", "素材不可用")
        return deliver(playback_medium(db, medium), request)

    @router.get("/media/{media_id}/status", response_model=MediaMetadata)
    def status(
        media_id: str,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        medium = db.get(Media, media_id)
        if not medium:
            raise DomainError(404, "media_missing", "素材不可用")
        return media_view(medium, db)

    return router


def mini_routes():
    router = APIRouter(prefix="/api/mini/v1", tags=["controlled published resources"])

    @router.get(
        "/cards/{card_id}/media/{media_id}/url",
        response_model=ResourceURL,
        dependencies=[Depends(write_transaction)],
    )
    def issue(
        card_id: str,
        media_id: str,
        request: Request,
        version_id: str | None = None,
        purpose: Literal["content", "summary"] = "content",
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        medium = db.get(Media, media_id)
        if purpose == "summary":
            version = summary_thumbnail(db, user.id, card_id, media_id, version_id)
        else:
            if not version_id:
                raise DomainError(422, "version_required", "请刷新后重新获取资源")
            _, version = published_card(db, card_id, version_id)
            image = db.get(Media, version.payload["image_id"])
            allowed = {
                version.payload["image_id"],
                version.payload["audio_id"],
                image.thumbnail_id if image else None,
            }
            if media_id not in allowed:
                raise DomainError(404, "media_missing", "素材不可用")
        if not medium or medium.state != "ready":
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
                purpose=purpose,
                expires_at=expires,
            )
        )
        return {"url": "/api/mini/v1/media/" + credential, "expires_at": timestamp(expires)}

    @router.head("/media/{credential}", include_in_schema=False)
    @router.get("/media/{credential}")
    def read(credential: str, request: Request, db: Session = Depends(database, scope="function")):
        now = request.app.state.clock()
        ticket = db.get(MediaTicket, digest(credential))
        if not ticket or ticket.expires_at <= now:
            raise DomainError(401, "resource_expired", "资源地址已失效，请重新获取")
        session = db.get(MiniSession, ticket.session_digest)
        if not session or session.expires_at <= now or session.user_id != ticket.user_id:
            raise DomainError(401, "login_required", "请主动登录后继续")
        if ticket.purpose == "summary":
            summary_thumbnail(
                db, ticket.user_id, ticket.card_id, ticket.media_id, ticket.version_id
            )
        elif ticket.purpose == "content":
            published_card(db, ticket.card_id, ticket.version_id)
        else:
            raise DomainError(404, "media_missing", "素材不可用")
        medium = db.get(Media, ticket.media_id)
        if not medium or medium.state != "ready":
            raise DomainError(404, "media_missing", "素材不可用")
        return deliver(playback_medium(db, medium), request)

    return router
