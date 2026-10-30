"""Version-bound word timestamps, conservative text matching and durable independent tasks."""

import base64
import re
import shutil
import subprocess
import tempfile
from datetime import timedelta
from difflib import SequenceMatcher
from pathlib import Path

from sqlalchemy import or_, select

from .content_models import Media, SettingCounter
from .database import timestamp, utc_now
from .errors import DomainError
from .learning_service import business_date
from .listening_models import (
    ListeningArticle,
    ListeningCandidate,
    ListeningJob,
    ListeningTimeline,
    ListeningVersion,
)
from .models import identifier
from .persistence import insert_once
from .security import fingerprint
from .storage import ObjectStorage

TOKEN = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]+(?:['’\-][A-Za-z]+)*(?![A-Za-z0-9_])")


def body_tokens(body):
    return list(TOKEN.finditer(body))


def alignment_tokens(body):
    """Exclude dialogue layout only, retaining original character offsets for readers."""
    lines = list(re.finditer(r"[^\n]+", body))
    speaker = re.compile(r"[ \t]*([A-Z][a-zA-Z]*(?:[ \t]+[A-Z][a-zA-Z]*){0,2}):[ \t]*(?=\S)")
    labels = [(line, speaker.match(line.group())) for line in lines]
    names = {match.group(1) for _, match in labels if match}
    if len(names) < 2:
        return body_tokens(body)
    excluded = []
    for index, (line, match) in enumerate(labels):
        if match:
            excluded.append((line.start(), line.start() + match.end()))
        elif (
            index + 1 < len(labels)
            and labels[index + 1][1]
            and re.fullmatch(r"[A-Z][A-Za-z’' \-]{0,119}", line.group().strip())
            and len(body_tokens(line.group())) <= 12
            and all(
                word.group()[0].isupper()
                or word.group()
                in {"a", "an", "the", "and", "or", "of", "in", "on", "at", "to", "for", "with"}
                for word in body_tokens(line.group())
            )
        ):
            # A separate heading immediately introduces a labeled dialogue turn.
            excluded.append((line.start(), line.end()))
    return [
        token
        for token in body_tokens(body)
        if not any(start <= token.start() < end for start, end in excluded)
    ]


def input_identity(db, payload):
    audio = db.get(Media, payload.get("audio_id")) if payload.get("audio_id") else None
    if not payload.get("body_en", "").strip() or not audio or audio.state != "ready":
        return None
    if audio.kind != "audio" or not audio.duration or not audio.playback_id:
        return None
    return fingerprint(
        {
            "body_en": payload["body_en"],
            "audio_sha256": audio.sha256,
            "audio_id": audio.id,
            "duration": audio.duration,
            "alignment": 1,
        }
    )


def ensure_timeline(db, payload, now):
    identity = input_identity(db, payload)
    if not identity:
        return None
    insert_once(
        db,
        ListeningTimeline,
        {
            "input_hash": identity,
            "body_en": payload["body_en"],
            "audio_id": payload["audio_id"],
            "state": "pending",
            "words": [],
        },
        ["input_hash"],
    )
    row = db.scalar(
        select(ListeningTimeline)
        .where(ListeningTimeline.input_hash == identity)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    previous_job = db.get(ListeningJob, row.job_id) if row.job_id else None
    if row.state != "ready" and (not previous_job or previous_job.state == "cancelled"):
        job = ListeningJob(input_hash=identity, state="pending", created_at=now, updated_at=now)
        db.add(job)
        db.flush()
        row.job_id = job.id
        row.state, row.error_code = "pending", None
    db.flush()
    return identity


def timeline_view(db, payload):
    identity = input_identity(db, payload)
    row = db.get(ListeningTimeline, identity) if identity else None
    return {
        "state": row.state if row else "missing",
        "input_hash": identity,
        "job_id": row.job_id if row else None,
        "words": row.words if row and row.state == "ready" else [],
        "reviewed_at": timestamp(row.reviewed_at) if row else None,
        "error_code": row.error_code if row else None,
    }


def validate_words(body, words, duration_ms, *, minimum_coverage=1.0, max_word_ms=10000):
    tokens = {(m.start(), m.end()): m.group() for m in alignment_tokens(body)}
    previous_end = previous_character = 0
    seen = set()
    if not words or not tokens or duration_ms <= 0:
        raise DomainError(422, "timeline_invalid", "时间轴没有可匹配的正文词项")
    for word in words:
        location = (word["start"], word["end"])
        begin, end = word["start_ms"], word["end_ms"]
        if (
            location not in tokens
            or location in seen
            or word["start"] < previous_character
            or begin < previous_end
            or end <= begin
            or end > duration_ms
            or end - begin > max_word_ms
            or not word["sentence_id"]
        ):
            raise DomainError(422, "timeline_invalid", "时间轴位置、顺序或音频时长校验未通过")
        seen.add(location)
        previous_end, previous_character = end, word["end"]
    if len(seen) / len(tokens) < minimum_coverage:
        raise DomainError(422, "timeline_coverage_low", "录音与正文匹配不足，请核对资料")
    return words


def align_words(body, recognized, duration_ms, *, minimum_coverage=1.0, max_word_ms=10000):
    """Monotonic sequence matching preserves repeated word positions and real pauses."""
    text = alignment_tokens(body)
    normalized = lambda word: word.casefold().replace("’", "'")  # noqa: E731
    actual = []
    for word in recognized:
        token = TOKEN.fullmatch(word.get("word", "").strip())
        if token:
            actual.append({**word, "word": token.group()})
    matcher = SequenceMatcher(
        None,
        [normalized(m.group()) for m in text],
        [normalized(w["word"]) for w in actual],
        autojunk=False,
    )
    matched = []
    for block in matcher.get_matching_blocks():
        for n in range(block.size):
            token, word = text[block.a + n], actual[block.b + n]
            sentence_id = str(len(re.findall(r"[.!?](?:\s|$)|\n", body[: token.start()])))
            matched.append(
                {
                    "start": token.start(),
                    "end": token.end(),
                    "start_ms": word["start_ms"],
                    "end_ms": word["end_ms"],
                    "sentence_id": sentence_id,
                }
            )
    if not actual or len(matched) / len(actual) < minimum_coverage:
        raise DomainError(422, "timeline_coverage_low", "识别结果包含过多不匹配词项")
    return validate_words(
        body, matched, duration_ms, minimum_coverage=minimum_coverage, max_word_ms=max_word_ms
    )


def active_input(db, identity):
    """A removed candidate/deleted article cannot be resurrected by a late provider result."""
    for article in db.scalars(
        select(ListeningArticle).where(ListeningArticle.deleted_at.is_(None))
    ):
        if input_identity(db, article.payload) == identity:
            return True
        if article.status == "published" and article.version_id:
            version = db.get(ListeningVersion, article.version_id)
            if version and version.input_hash == identity:
                return True
    return any(
        input_identity(db, c.payload) == identity
        for c in db.scalars(
            select(ListeningCandidate).where(
                ListeningCandidate.removed.is_(False),
                ListeningCandidate.article_id.is_(None),
                ListeningCandidate.state.not_in(["unreadable", "duplicate"]),
            )
        )
    )


class TencentAlignment:
    """Tencent ASR CreateRecTask/DescribeTaskStatus, using official SDK signing."""

    def __init__(self, settings):
        if not settings.asr_secret_id or not settings.asr_secret_key:
            raise DomainError(503, "asr_unconfigured", "自动时间轴服务尚未配置")
        from tencentcloud.common import credential  # type: ignore[import-untyped]
        from tencentcloud.common.common_client import CommonClient  # type: ignore[import-untyped]
        from tencentcloud.common.profile.client_profile import ClientProfile  # type: ignore[import-untyped]
        from tencentcloud.common.profile.http_profile import HttpProfile  # type: ignore[import-untyped]

        self.settings = settings
        profile = ClientProfile(
            httpProfile=HttpProfile(endpoint="asr.tencentcloudapi.com", reqTimeout=30)
        )
        self.client = CommonClient(
            "asr",
            "2019-06-14",
            credential.Credential(settings.asr_secret_id, settings.asr_secret_key),
            settings.asr_region,
            profile,
        )

    def submit(self, audio):
        # Caller prepares a full mono recognition copy; original media remains private.
        if len(audio) > 5 * 1024 * 1024:
            raise DomainError(
                422, "asr_input_too_large", "识别专用副本仍超出服务商限制，请由运维核对提交方式"
            )
        response = self.call(
            "CreateRecTask",
            {
                "EngineModelType": self.settings.asr_engine,
                "ChannelNum": 1,
                "ResTextFormat": 1,
                "SourceType": 1,
                "Data": base64.b64encode(audio).decode(),
                "DataLen": len(audio),
            },
        )
        return str(response["Response"]["Data"]["TaskId"])

    def poll(self, task_id):
        response = self.call("DescribeTaskStatus", {"TaskId": int(task_id)})
        data = response["Response"]["Data"]
        if data["Status"] in {0, 1}:
            return None
        if data["Status"] != 2:
            raise DomainError(503, "asr_recognition_failed", "录音识别失败，请核对后重试")
        words = []
        for sentence in data.get("ResultDetail") or []:
            offset = sentence["StartMs"]
            for word in sentence.get("Words") or []:
                words.append(
                    {
                        "word": word["Word"],
                        "start_ms": offset + word["OffsetStartMs"],
                        "end_ms": offset + word["OffsetEndMs"],
                    }
                )
        return words

    def call(self, action, payload):
        from tencentcloud.common.exception.tencent_cloud_sdk_exception import (  # type: ignore[import-untyped]
            TencentCloudSDKException,
        )

        try:
            return self.client.call_json(action, payload)
        except TencentCloudSDKException as error:
            code = error.get_code() or ""
            if code.startswith(("AuthFailure", "UnauthorizedOperation")):
                safe = "asr_permission_denied"
            elif code.startswith(("LimitExceeded", "RequestLimitExceeded")):
                safe = "asr_rate_limited"
            elif code.startswith(("InvalidParameter", "MissingParameter")):
                safe = "asr_request_invalid"
            else:
                safe = (
                    "asr_submission_unknown"
                    if action == "CreateRecTask"
                    else "asr_poll_unavailable"
                )
            raise DomainError(503, safe, "时间轴识别服务暂不可用，请按真实状态处理") from None


def recognition_copy(data, duration):
    """A full 16kHz mono 32kbps copy for ASR; never clip or alter playback resources."""
    executable = shutil.which("ffmpeg")
    if not executable:
        raise DomainError(503, "asr_decoder_unavailable", "识别音频预处理暂不可用")
    with tempfile.TemporaryDirectory(prefix="juya-listening-asr-") as directory:
        source, target = Path(directory) / "source", Path(directory) / "recognition.mp3"
        source.write_bytes(data)
        try:
            subprocess.run(
                [
                    executable,
                    "-nostdin",
                    "-v",
                    "error",
                    "-xerror",
                    "-threads",
                    "1",
                    "-protocol_whitelist",
                    "file,pipe",
                    "-i",
                    str(source),
                    "-map",
                    "0:a:0",
                    "-vn",
                    "-sn",
                    "-dn",
                    "-map_metadata",
                    "-1",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "-codec:a",
                    "libmp3lame",
                    "-b:a",
                    "32k",
                    str(target),
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )
            output = target.read_bytes()
            from .media_api import decoded_audio

            _, actual_duration = decoded_audio(output)
            if abs(actual_duration - duration) > max(0.25, duration * 0.005):
                raise ValueError("recognition copy duration mismatch")
            if len(output) > 5 * 1024 * 1024:
                raise DomainError(
                    422, "asr_input_too_large", "识别专用完整副本超出服务商限制，需核对提交方式"
                )
            return output
        except (OSError, ValueError, subprocess.SubprocessError):
            raise DomainError(
                503, "asr_preprocessing_failed", "完整识别副本校验失败，请重试"
            ) from None


def run_timeline_job(settings, sessions, job_id, *, provider=None, clock=utc_now):
    """One bounded provider action per lease; poll IDs persist across worker restarts."""
    now, lease = clock(), identifier()
    with sessions.begin() as db:
        job = db.scalar(select(ListeningJob).where(ListeningJob.id == job_id).with_for_update())
        if not job or job.state not in {"pending", "processing"}:
            return
        if job.lease_until and job.lease_until > now:
            return
        row = db.get(ListeningTimeline, job.input_hash)
        if not row or row.job_id != job.id or not active_input(db, job.input_hash):
            job.state, job.updated_at = "cancelled", now
            if row and row.job_id == job.id:
                row.state, row.error_code = "missing", "input_removed"
            return
        if job.state == "processing" and not job.provider_task_id and job.attempts:
            # A lease expired inside a submission window. The provider may have accepted
            # it before the process died, so automatic resubmission could duplicate cost.
            job.state, row.state = "failed", "needs_attention"
            job.error_code = row.error_code = "asr_submission_unknown"
            job.lease_until, job.updated_at = None, now
            return
        job.lease_token, job.lease_until = lease, now + timedelta(minutes=2)
        job.state, row.state, job.updated_at = "processing", "processing", now
        identity, provider_id = job.input_hash, job.provider_task_id
        medium = db.get(Media, row.audio_id)
        audio_key, duration, body = medium.storage_key, medium.duration, row.body_en
        if not provider_id:
            counter_name = "listening_asr:" + business_date(now).isoformat()
            insert_once(db, SettingCounter, {"name": counter_name, "value": 0}, ["name"])
            budget = db.scalar(
                select(SettingCounter).where(SettingCounter.name == counter_name).with_for_update()
            )
            if budget.value >= settings.listening_asr_daily_budget:
                job.state, row.state = "failed", "failed"
                job.error_code = row.error_code = "asr_budget_exceeded"
                job.lease_until = None
                return
            budget.value += 1
            job.attempts += 1
    try:
        gateway = provider or TencentAlignment(settings)
        if not provider_id:
            source = ObjectStorage(settings).read(audio_key)
            provider_id = gateway.submit(recognition_copy(source, duration))
            with sessions.begin() as db:
                job = db.get(ListeningJob, job_id)
                if job.lease_token != lease:
                    return
                job.provider_task_id = provider_id
        words = gateway.poll(provider_id)
        if words is not None:
            result = align_words(
                body,
                words,
                round(duration * 1000),
                minimum_coverage=settings.listening_alignment_minimum_coverage,
                max_word_ms=settings.listening_alignment_max_word_ms,
            )
        else:
            result = None
        error = None
    except DomainError as exc:
        error, result = exc.code, None
    except Exception:
        error, result = "asr_poll_unavailable" if provider_id else "asr_submission_unknown", None
    with sessions.begin() as db:
        job = db.scalar(select(ListeningJob).where(ListeningJob.id == job_id).with_for_update())
        row = db.get(ListeningTimeline, identity)
        if job.lease_token != lease or not row or row.job_id != job.id:
            return
        job.lease_until, job.updated_at = None, clock()
        if not active_input(db, identity):
            job.state = "cancelled"
            row.state, row.error_code = "missing", "input_removed"
            return
        if error == "asr_poll_unavailable":
            # Unknown polling response retains the accepted provider ID; never resubmit.
            job.state, row.state = "processing", "processing"
            job.error_code = row.error_code = error
        elif error:
            job.state = "failed"
            row.state = (
                "needs_attention"
                if error in {"timeline_invalid", "timeline_coverage_low", "asr_submission_unknown"}
                else "failed"
            )
            job.error_code = row.error_code = error
        elif result is not None:
            job.state, row.state, row.words = "succeeded", "ready", result
            job.error_code = row.error_code = None


def pending_jobs(sessions, now):
    with sessions() as db:
        return list(
            db.scalars(
                select(ListeningJob.id)
                .where(
                    ListeningJob.state.in_(["pending", "processing"]),
                    or_(ListeningJob.lease_until.is_(None), ListeningJob.lease_until <= now),
                )
                .order_by(ListeningJob.updated_at, ListeningJob.created_at)
                .limit(20)
            )
        )
