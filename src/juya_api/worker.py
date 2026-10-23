"""Celery execution with database leases; payloads never enter broker messages."""

import hashlib
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from celery import Celery  # type: ignore[import-untyped]

from .config import Settings
from .content_models import Media
from .database import make_database, naive_utc
from .errors import DomainError
from .jobs import claim, fail, finish
from .storage import ObjectStorage


def prepare_media(settings, sessions, payload):
    """Decode in the isolated worker, outside the HTTP and database transactions."""
    from .audio_processing import playback_mp3
    from .media_api import decoded_audio, decoded_image

    with sessions() as db:
        medium = db.get(Media, payload["media_id"])
        if not medium:
            raise DomainError(404, "media_missing", "素材不可用")
        kind, source_key, size = medium.kind, medium.storage_key, medium.size
        owner_kind, owner_id, media_id = medium.owner_kind, medium.owner_id, medium.id
        previous_type, previous_duration = medium.content_type, medium.duration
        previous_stage, active_job_id = medium.processing_stage, medium.job_id
        expected_hash = medium.sha256
        original_name = None
        if kind == "audio" and owner_kind == "admin":
            from sqlalchemy import select

            from .admin_action_models import AdminMediaSource
            from .import_models import ImportFile

            source = db.get(AdminMediaSource, media_id)
            imported = (
                db.scalar(select(ImportFile).where(ImportFile.media_id == media_id).limit(1))
                if not source
                else None
            )
            original_name = source.original_name if source else imported.name if imported else None
    storage = ObjectStorage(settings)
    data = storage.read(source_key)
    if (
        len(data) != size
        or hashlib.sha256(data).hexdigest() != expected_hash
        or len(data) > settings.audio_limit_mb * 1024 * 1024
    ):
        raise DomainError(422, "media_invalid", "素材无法读取")
    thumbnail = None
    playback = None
    if kind in {"image", "avatar"}:
        content_type, width, height, thumbnail_data, dimensions = decoded_image(data)
        thumb_id = str(uuid5(NAMESPACE_URL, media_id + ":thumbnail"))
        checksum = hashlib.sha256(thumbnail_data).hexdigest()
        key = f"{settings.environment}/media/{thumb_id}/{checksum}"
        storage.put(key, thumbnail_data, "image/webp")
        thumbnail = dict(
            id=thumb_id,
            owner_kind=owner_kind,
            owner_id=owner_id,
            kind="thumbnail",
            state="ready",
            storage_key=key,
            content_type="image/webp",
            size=len(thumbnail_data),
            sha256=checksum,
            width=dimensions[0],
            height=dimensions[1],
        )
        metadata = dict(
            content_type=content_type, width=width, height=height, thumbnail_id=thumb_id
        )
    else:
        if previous_stage == "converting" and previous_duration:
            content_type, duration = previous_type, previous_duration
        else:
            content_type, duration = decoded_audio(data)
        if original_name:
            from pathlib import PurePosixPath

            expected_type = {
                ".wav": "audio/wav",
                ".mp3": "audio/mpeg",
                ".m4a": "audio/mp4",
                ".aac": "audio/aac",
            }.get(PurePosixPath(original_name).suffix.lower())
            if expected_type != content_type:
                raise DomainError(
                    422, "audio_format_mismatch", "音频真实格式与文件后缀不一致，请上传原始格式文件"
                )
        with sessions.begin() as db:
            row = db.get(Media, media_id)
            if not row or row.job_id != active_job_id:
                raise DomainError(409, "media_changed", "素材处理状态已更新")
            row.content_type, row.duration, row.processing_stage = (
                content_type,
                duration,
                "converting",
            )
        output = playback_mp3(data, content_type, duration, settings.audio_limit_mb * 1024 * 1024)
        playback_id = media_id
        if content_type != "audio/mpeg":
            playback_id = str(uuid5(NAMESPACE_URL, media_id + ":mp3-v1"))
            checksum = hashlib.sha256(output).hexdigest()
            key = f"{settings.environment}/media/{playback_id}/{checksum}"
            storage.put(key, output, "audio/mpeg")
            playback = dict(
                id=playback_id,
                owner_kind=owner_kind,
                owner_id=owner_id,
                kind="audio_playback",
                state="ready",
                storage_key=key,
                content_type="audio/mpeg",
                size=len(output),
                sha256=checksum,
                duration=duration,
            )
        metadata = dict(
            content_type=content_type,
            duration=duration,
            playback_id=playback_id,
            processing_stage="ready",
        )

    def apply(db, job):
        row = db.get(Media, media_id)
        if not row or row.job_id != job.id:
            raise DomainError(409, "media_changed", "素材处理状态已更新")
        for artifact in [thumbnail, playback]:
            if artifact:
                existing = db.get(Media, artifact["id"])
                if existing and existing.sha256 != artifact["sha256"]:
                    raise DomainError(409, "media_derivative_changed", "播放资源处理结果已变化")
                if not existing:
                    db.add(Media(**artifact, created_at=job.updated_at))
        for name, value in metadata.items():
            setattr(row, name, value)
        row.state = "ready"

    return {"media_id": media_id}, apply


def run_job(settings, sessions, job_id, *, clock=None, tts=None):
    """Only the winning lease may commit decoded output or final failure state."""

    def now():
        return naive_utc(clock() if clock else datetime.now(UTC))

    job = claim(sessions, job_id, now(), settings=settings, role=settings.worker_role)
    if not job:
        return
    try:
        if job["kind"] == "media.decode":
            result, apply = prepare_media(settings, sessions, job["payload"])
        elif job["kind"] == "import.parse":
            from .import_service import prepare_parse

            result, apply = prepare_parse(settings, sessions, job, clock=now)
        elif job["kind"] == "import.save":
            from .import_service import prepare_save

            result, apply = prepare_save(settings, sessions, job, now())
        elif job["kind"] == "tts.synthesize":
            from .pronunciation import prepare

            result, apply = prepare(settings, sessions, job, now(), tts)
        elif job["kind"] == "card.action":
            result = {"card_id": job["payload"]["card_id"]}

            def apply(db, row):
                from .admin_action_api import ActionSelection, validate_snapshot
                from .content_service import catalog_lock, lifecycle_action
                from .models import Administrator
                from .transactions import actor_lock

                if job["owner_kind"] != "admin":
                    raise DomainError(403, "action_role_invalid", "管理任务归属无效")
                actor_lock(db, db.get(Administrator, job["owner_id"]), "admin")
                payload = job["payload"]
                selection = ActionSelection.model_validate(
                    {k: v for k, v in payload.items() if k != "action"}
                )
                catalog_lock(db)
                validate_snapshot(db, selection)
                lifecycle_action(
                    db,
                    selection.card_id,
                    selection.revision,
                    payload["action"],
                    job["owner_id"],
                    now(),
                )
        elif job["kind"] == "card.publish":
            result = {"card_id": job["payload"]["card_id"]}

            def apply(db, row):
                from .content_service import publish_version, require_card
                from .models import Administrator
                from .transactions import actor_lock

                actor_lock(db, db.get(Administrator, job["owner_id"]), "admin")
                payload = job["payload"]
                publish_version(
                    db,
                    require_card(db, payload["card_id"]),
                    job["owner_id"],
                    payload["revision"],
                    payload["preview_id"],
                    now(),
                )
        else:
            raise DomainError(422, "task_kind_invalid", "任务类型不可用")
        finish(sessions, job_id, job["lease"], now(), result, apply=apply)
    except Exception as error:
        code = error.code if isinstance(error, DomainError) else "task_failed"
        temporary = not isinstance(error, DomainError) or error.status >= 500
        fail(sessions, job_id, job["lease"], now(), code, temporary=temporary)


def celery_app(settings=None):
    """Use JSON-only broker envelopes with no backend results or provider payloads."""
    settings = settings or Settings()
    app = Celery("juya", broker=settings.redis_url)
    if settings.worker_role:
        app.conf.task_default_queue = "juya-" + settings.worker_role
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        task_ignore_result=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        worker_concurrency=1,
        task_soft_time_limit=180,
        task_time_limit=240,
        broker_connection_retry_on_startup=True,
        broker_connection_timeout=3,
        task_publish_retry=False,
        broker_transport_options={"visibility_timeout": 300},
    )

    @app.task(name="juya.execute", acks_late=True, reject_on_worker_lost=True)
    def execute(job_id):
        engine, sessions = make_database(settings)
        try:
            run_job(settings, sessions, job_id)
        finally:
            engine.dispose()

    return app
