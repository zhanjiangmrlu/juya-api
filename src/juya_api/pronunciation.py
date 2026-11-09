"""Controlled, cached English speech without sending learner data to the provider."""

import base64
import hashlib
import json
from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

from .content_models import CardDraft, Media, SettingCounter
from .content_service import published_card, require_card, revision_matches
from .errors import DomainError
from .import_models import ImportItem
from .import_service import owned_batch
from .job_models import Job
from .jobs import enqueue
from .learning_service import business_date
from .persistence import insert_once
from .pronunciation_models import Pronunciation
from .security import fingerprint
from .storage import ObjectStorage


def configuration(settings):
    """Keep cache identity tied to every actual synthesis parameter."""
    return {
        "VoiceType": settings.tts_voice_type,
        "PrimaryLanguage": 2,
        "SampleRate": 16000,
        "Codec": settings.tts_codec,
        "Speed": 0,
        "Volume": 0,
        "ModelType": 1,
    }


def reference(db, settings, role, card_id, word_id, version_id=None, revision=None):
    """Resolve a saved controlled vocabulary reference, never client-supplied speech text."""
    if (version_id is None) == (revision is None) or (role == "mini" and not version_id):
        raise DomainError(422, "word_reference_required", "请重新打开词汇后试听")
    if version_id:
        _, version = published_card(db, card_id, version_id)
        content = version.payload
    else:
        require_card(db, card_id)
        content = revision_matches(db.get(CardDraft, card_id), revision).payload
    return word_reference(settings, content, word_id)


def import_reference(db, settings, admin_id, batch_id, item_id, word_id, revision):
    """Resolve only an administrator's saved review revision without creating a Card."""
    owned_batch(db, batch_id, admin_id)
    item = db.scalar(
        select(ImportItem).where(ImportItem.id == item_id).execution_options(populate_existing=True)
    )
    if not item or item.batch_id != batch_id or not item.readable:
        raise DomainError(404, "word_missing", "未找到这条核对词汇")
    if item.revision != revision:
        raise DomainError(409, "import_changed", "核对资料已变化，请重新试听")
    return word_reference(settings, item.content, word_id)


def word_reference(settings, content, word_id):
    """Share cache rules across saved cards and controlled import staging references."""
    word = next((w for w in content["vocabulary"] if w["id"] == word_id), None)
    if not word:
        raise DomainError(404, "word_missing", "未找到这条词汇")
    reading = (word.get("pronunciation_text") or word["english"]).strip()
    if (
        not reading
        or len(reading) > 300
        or any(c in reading for c in "<>&")
        or not reading.isprintable()
    ):
        raise DomainError(422, "pronunciation_unconfirmed", "请先核对词汇的朗读文字")
    config = configuration(settings)
    cache_key = fingerprint(
        {"spelling": word["english"], "reading": reading, "configuration": config}
    )
    return word, reading, config, cache_key


def status(db, cache_key):
    """Look up durable state without starting cloud work from a read request."""
    cache = db.get(Pronunciation, cache_key)
    job = db.get(Job, cache.job_id) if cache and cache.job_id else None
    if cache and cache.media_id and job and job.state == "succeeded":
        state = "ready"
    elif job and job.state == "failed":
        state = "failed"
    else:
        state = "processing" if job else "missing"
    return {
        "state": state,
        "job_id": job.id if job else None,
        "error_code": job.error_code if state == "failed" and job else None,
        "url": None,
        "retry_after": 1 if state == "processing" else None,
    }


def request(db, settings, actor, role, word, reading, config, cache_key, now, *, prewarm=None):
    """Request controlled speech for an authenticated actor, preserving existing ownership."""
    return request_for_owner(
        db, settings, actor.id, role, word, reading, config, cache_key, now, prewarm=prewarm
    )


def request_for_owner(
    db, settings, owner_id, role, word, reading, config, cache_key, now, *, prewarm=None
):
    """Reserve shared speech work independently of a User or personal operation receipt."""
    # Serialize cache-pointer writers before reading the job, never take a cache
    # lock and subsequently wait for its old job (finish locks in reverse order).
    name = fingerprint({"tts_cache_lock": cache_key})
    insert_once(db, SettingCounter, {"name": name, "value": 0}, ["name"])
    db.scalar(select(SettingCounter).where(SettingCounter.name == name).with_for_update())
    for _ in range(3):
        snapshot = db.scalar(
            select(Pronunciation)
            .where(Pronunciation.cache_key == cache_key)
            .execution_options(populate_existing=True)
        )
        previous_id = snapshot.job_id if snapshot else None
        previous = (
            db.scalar(
                select(Job)
                .where(Job.id == previous_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if previous_id
            else None
        )
        if not snapshot:
            insert_once(
                db,
                Pronunciation,
                {
                    "cache_key": cache_key,
                    "spelling": word["english"],
                    "reading": reading,
                    "configuration": config,
                    "created_at": now,
                },
                ["cache_key"],
            )
        cache = db.scalar(
            select(Pronunciation)
            .where(Pronunciation.cache_key == cache_key)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if cache.job_id != previous_id:
            continue
        promote = (
            not prewarm
            and previous
            and previous.kind == "tts.prewarm"
            and previous.state in {"queued", "retry"}
        )
        if (
            previous
            and previous.state != "failed"
            and not promote
            and not (previous.state == "succeeded" and (previous.result or {}).get("skipped"))
        ):
            return status(db, cache_key)
        if (
            previous
            and previous.state == "failed"
            and now < previous.updated_at + timedelta(seconds=60)
        ):
            raise DomainError(429, "tts_cooldown", "发音暂不可用，请稍后重试")
        if promote and previous:
            previous.state, previous.updated_at = "succeeded", now
            previous.result = {"skipped": "foreground_promoted"}
            previous.error_code, previous.lease, previous.lease_expires_at = None, None, None
        job = enqueue(
            db,
            "tts.prewarm" if prewarm else "tts.synthesize",
            role,
            owner_id,
            {"cache_key": cache_key, **(prewarm or {})},
            now,
            settings=settings,
        )
        cache.job_id, cache.media_id = job.id, None
        db.flush()
        return status(db, cache_key)
    raise DomainError(409, "tts_changed", "发音任务已更新，请重试")


def reserve_budget(db, settings, now):
    """Count every attempted provider call, including unknown/failed responses and retries."""
    name = "tts:" + business_date(now).isoformat()
    insert_once(db, SettingCounter, {"name": name, "value": 0}, ["name"])
    row = db.scalar(select(SettingCounter).where(SettingCounter.name == name).with_for_update())
    if row.value >= settings.tts_daily_budget:
        raise DomainError(429, "tts_budget_exceeded", "今日发音生成额度暂不可用，请稍后再试")
    row.value += 1


class TencentSpeech:
    def __init__(self, settings):
        if not settings.tts_secret_id or not settings.tts_secret_key:
            raise DomainError(422, "tts_unconfigured", "发音服务暂不可用")
        from tencentcloud.common import credential  # type: ignore[import-untyped]
        from tencentcloud.common.profile.client_profile import ClientProfile  # type: ignore[import-untyped]
        from tencentcloud.common.profile.http_profile import HttpProfile  # type: ignore[import-untyped]
        from tencentcloud.tts.v20190823 import tts_client  # type: ignore[import-untyped]

        http = HttpProfile(endpoint="tts.tencentcloudapi.com", reqTimeout=30)
        profile = ClientProfile(httpProfile=http)
        self.client = tts_client.TtsClient(
            credential.Credential(settings.tts_secret_id, settings.tts_secret_key), "", profile
        )

    def synthesize(self, text, config, session_id):
        """Use plain confirmed reading; display IPA is never interpreted as SSML."""
        from tencentcloud.common.exception.tencent_cloud_sdk_exception import (  # type: ignore[import-untyped]
            TencentCloudSDKException,
        )
        from tencentcloud.tts.v20190823 import models  # type: ignore[import-untyped]

        body = models.TextToVoiceRequest()
        body.from_json_string(json.dumps({"Text": text, "SessionId": session_id, **config}))
        try:
            response = self.client.TextToVoice(body)
            data = base64.b64decode(response.Audio, validate=True)
            if not data or len(data) > 5 * 1024 * 1024:
                raise DomainError(422, "tts_audio_invalid", "发音暂不可用")
            return data
        except TencentCloudSDKException as error:
            code = error.get_code()
            temporary = code.startswith(
                (
                    "InternalError",
                    "LimitExceeded",
                    "RequestLimitExceeded",
                    "ClientNetworkError",
                    "ResourceUnavailable",
                )
            )
            raise DomainError(
                503 if temporary else 422,
                "tts_temporary" if temporary else "tts_permanent",
                "发音暂不可用",
            ) from None
        except (ValueError, TypeError):
            raise DomainError(422, "tts_audio_invalid", "发音暂不可用") from None


def prepare(settings, sessions, job, now, provider=None):
    """Synthesize outside transactions, then publish validated audio only under a current lease."""
    from .media_api import decoded_audio

    if job["kind"] == "tts.prewarm":
        with sessions() as db:
            if not prewarm_current(db, settings, job["payload"]):
                return {"skipped": "publication_or_configuration_changed"}, None
    cache_key = job["payload"]["cache_key"]
    with sessions() as db:
        cache = db.get(Pronunciation, cache_key)
        if not cache or cache.job_id != job["id"]:
            raise DomainError(409, "tts_changed", "发音任务已更新")
        reading, config = cache.reading, cache.configuration
    provider = provider or TencentSpeech(settings)
    with sessions.begin() as db:
        reserve_budget(db, settings, now)
    data = provider.synthesize(reading, config, job["id"])
    content_type, duration = decoded_audio(data)
    media_id = str(uuid5(NAMESPACE_URL, "juya-pronunciation:" + cache_key))
    checksum = hashlib.sha256(data).hexdigest()
    storage_key = f"{settings.environment}/pronunciation/{media_id}/{checksum}"
    ObjectStorage(settings).put(storage_key, data, content_type)

    result = {"cache_key": cache_key}

    def apply(db, row):
        if job["kind"] == "tts.prewarm" and not prewarm_current(db, settings, job["payload"]):
            result.clear()
            result["skipped"] = "publication_or_configuration_changed"
            return
        cache = db.scalar(
            select(Pronunciation)
            .where(Pronunciation.cache_key == cache_key)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not cache or cache.job_id != row.id:
            raise DomainError(409, "tts_changed", "发音任务已更新")
        if not db.get(Media, media_id):
            db.add(
                Media(
                    id=media_id,
                    owner_kind="system",
                    owner_id="pronunciation",
                    kind="pronunciation",
                    state="ready",
                    storage_key=storage_key,
                    content_type=content_type,
                    sha256=checksum,
                    size=len(data),
                    duration=duration,
                    created_at=now,
                )
            )
            db.flush()
        cache.media_id = media_id

    return result, apply


def enqueue_prewarm(db, settings, card_id, version_id, admin_id, now, *, offset=0, revive=False):
    """Accept one deterministic batch per publication/configuration in its transaction."""
    from .security import encrypt

    config = configuration(settings)
    payload = {
        "card_id": card_id,
        "version_id": version_id,
        "configuration": config,
        "offset": offset,
    }
    job_id = str(uuid5(NAMESPACE_URL, "juya-prewarm:" + fingerprint(payload)))
    insert_once(
        db,
        Job,
        {
            "id": job_id,
            "kind": "pronunciation.prewarm",
            "owner_kind": "admin",
            "owner_id": admin_id,
            "payload": encrypt(settings, json.dumps(payload)),
            "state": "queued",
            "attempts": 0,
            "max_attempts": 3,
            "available_at": now,
            "dispatch_after": now,
            "created_at": now,
            "updated_at": now,
        },
        ["id"],
    )
    row = db.scalar(
        select(Job)
        .where(Job.id == job_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    skipped = row.state == "succeeded" and isinstance((row.result or {}).get("skipped"), str)
    if row.state == "failed" or skipped or (revive and row.state == "succeeded"):
        row.state, row.attempts, row.result = "queued", 0, None
        row.available_at, row.dispatch_after, row.updated_at = now, now, now
        row.error_code, row.lease, row.lease_expires_at = None, None, None
    return job_id


def prewarm_current(db, settings, payload):
    """Background speech must still belong to the current live publication and voice."""
    from .content_models import Card

    card = db.scalar(
        select(Card).where(Card.id == payload["card_id"]).execution_options(populate_existing=True)
    )
    return bool(
        card
        and card.deleted_at is None
        and card.status == "published"
        and card.current_version_id == payload["version_id"]
        and configuration(settings) == payload["configuration"]
    )


def prepare_prewarm(settings, sessions, job, now):
    """Expand at most 32 exact body references; each controlled word fails independently."""
    from types import SimpleNamespace

    from .content_models import CardVersion
    from .dictionary import body_references, controlled_target

    result: dict = {"accepted": 0, "skipped": 0}

    def apply(db, row):
        payload = job["payload"]
        if not prewarm_current(db, settings, payload):
            result["skipped"] = "publication_or_configuration_changed"
            return
        version = db.get(CardVersion, payload["version_id"])
        refs = body_references(version.payload, version.id)
        offset = payload.get("offset", 0)
        for ref in refs[offset : offset + 32]:
            try:
                target = controlled_target(db, settings, payload["card_id"], ref)
                if not target.reading:
                    result["skipped"] += 1
                    continue
                with db.begin_nested():
                    request(
                        db,
                        settings,
                        SimpleNamespace(id=job["owner_id"]),
                        "admin",
                        {"english": target.word},
                        target.reading,
                        target.config,
                        target.cache_key,
                        now,
                        prewarm={k: payload[k] for k in ("card_id", "version_id", "configuration")},
                    )
                result["accepted"] += 1
            except DomainError:
                result["skipped"] += 1
        if offset + 32 < len(refs):
            enqueue_prewarm(
                db,
                settings,
                payload["card_id"],
                payload["version_id"],
                job["owner_id"],
                now,
                offset=offset + 32,
                revive=True,
            )

    return result, apply
