"""Original bytes and normalized playback stay separate and version-authorized."""

import hashlib
import shutil
import subprocess

import pytest
from sqlalchemy import select

from juya_api.content_models import Media
from juya_api.storage import ObjectStorage

from .content_helpers import content, draft, key, process_jobs, publish, recording


def test_forged_extension_is_rejected_after_actual_decode_and_unsupported_upload_is_explicit(admin):
    forged = admin.post(
        "/api/admin/v1/media?kind=audio",
        headers=key(),
        files={"file": ("伪造.mp3", recording(), "audio/mpeg")},
    ).json()
    process_jobs(admin)
    status = admin.get(f"/api/admin/v1/media/{forged['id']}/status").json()
    assert status["state"] == "failed"
    assert status["error_code"] == "audio_format_mismatch"
    unsupported = admin.post(
        "/api/admin/v1/media?kind=audio",
        headers=key(),
        files={"file": ("不支持.ogg", b"OggSdata", "audio/ogg")},
    )
    assert unsupported.status_code == 422
    assert unsupported.json()["error"]["code"] == "audio_format_unsupported"


def test_wav_original_is_retained_but_admin_and_learner_stream_verified_mp3(system, admin, mini):
    payload = content(admin)
    media_id = payload["audio_id"]
    metadata = admin.get(f"/api/admin/v1/media/{media_id}/status").json()
    assert metadata["content_type"] == "audio/wav"
    assert metadata["playback_content_type"] == "audio/mpeg"
    assert metadata["playback_id"] != media_id
    storage = ObjectStorage(system["settings"])
    with system["sessions"]() as db:
        original = db.get(Media, media_id)
        assert storage.read(original.storage_key) == recording()
        assert original.sha256 == hashlib.sha256(recording()).hexdigest()
    playback = admin.get(f"/api/admin/v1/media/{media_id}")
    assert playback.headers["content-type"] == "audio/mpeg"
    assert not playback.content.startswith(b"RIFF")
    card = draft(admin, payload)
    version = publish(admin, card)["current_version_id"]
    ticket = mini.get(
        f"/api/mini/v1/cards/{card['id']}/media/{media_id}/url?version_id={version}"
    ).json()["url"]
    partial = mini.get(ticket, headers={"Range": "bytes=0-15"})
    assert partial.status_code == 206
    assert partial.content == playback.content[:16]
    assert (
        mini.get(
            f"/api/mini/v1/cards/{card['id']}/media/{metadata['playback_id']}/url?version_id={version}"
        ).status_code
        == 404
    )
    admin.post(f"/api/admin/v1/cards/{card['id']}/offline", headers=key(), json={"revision": 1})
    assert mini.get(ticket).status_code == 410


@pytest.mark.parametrize(
    "extension,options",
    [
        ("MP3", ["-codec:a", "libmp3lame"]),
        ("M4A", ["-codec:a", "aac"]),
        ("WAV", ["-codec:a", "pcm_s16le"]),
        ("AAC", ["-codec:a", "aac", "-f", "adts"]),
    ],
)
def test_all_real_audio_formats_produce_complete_mp3_playback(admin, tmp_path, extension, options):
    assert shutil.which("ffmpeg"), "Real FFmpeg is required for conversion verification"
    path = tmp_path / ("sample." + extension.lower())
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            *options,
            str(path),
        ],
        check=True,
    )
    upload = admin.post(
        "/api/admin/v1/media?kind=audio",
        headers=key(),
        files={"file": ("完整音频." + extension, path.read_bytes(), "text/plain")},
    ).json()
    process_jobs(admin)
    metadata = admin.get(f"/api/admin/v1/media/{upload['id']}/status").json()
    assert metadata["state"] == "ready", metadata
    assert metadata["playback_content_type"] == "audio/mpeg"
    from juya_api.media_api import decoded_audio

    output = admin.get(f"/api/admin/v1/media/{upload['id']}").content
    kind, duration = decoded_audio(output)
    assert kind == "audio/mpeg"
    assert abs(duration - 2) < 0.25


def test_conversion_failure_keeps_original_and_retry_creates_only_one_derivative(
    system, admin, monkeypatch
):
    import juya_api.audio_processing as processing
    from juya_api.errors import DomainError

    real = processing.playback_mp3

    def fail(*args, **kwargs):
        raise DomainError(503, "audio_conversion_unavailable", "音频转换暂不可用")

    monkeypatch.setattr(processing, "playback_mp3", fail)
    upload = admin.post(
        "/api/admin/v1/media?kind=audio",
        headers=key(),
        files={"file": ("完整.WAV", recording(), "audio/wav")},
    ).json()
    process_jobs(admin)
    from juya_api.job_models import Job

    with system["sessions"].begin() as db:
        job = db.get(Job, upload["job_id"])
        job.state = "failed"
        row = db.get(Media, upload["id"])
        assert ObjectStorage(system["settings"]).read(row.storage_key) == recording()
    monkeypatch.setattr(processing, "playback_mp3", real)
    admin.post(f"/api/admin/v1/media/{upload['id']}/retry", headers=key())
    process_jobs(admin)
    assert admin.get(f"/api/admin/v1/media/{upload['id']}/status").json()["state"] == "ready"
    with system["sessions"]() as db:
        assert len(list(db.scalars(select(Media).where(Media.kind == "audio_playback")))) == 1


@pytest.mark.parametrize(
    "extension,options",
    [
        ("MP3", ["-codec:a", "libmp3lame"]),
        ("M4A", ["-codec:a", "aac"]),
        ("WAV", ["-codec:a", "pcm_s16le"]),
        ("AAC", ["-codec:a", "aac", "-f", "adts"]),
    ],
)
@pytest.mark.parametrize("mode", ["zip", "docx"])
def test_each_import_entry_accepts_real_formats_and_delivers_mp3(
    admin, tmp_path, extension, options, mode
):
    from .test_imports import archive, document

    path = tmp_path / ("sample." + extension.lower())
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            *options,
            str(path),
        ],
        check=True,
    )
    batch = admin.post("/api/admin/v1/imports", headers=key(), json={"mode": mode}).json()
    prefix = f"/api/admin/v1/imports/{batch['id']}"
    if mode == "zip":
        package = archive(
            [
                ("同名文件夹/内容.docx", document("音频卡")),
                ("同名文件夹/完整音频." + extension, path.read_bytes()),
            ]
        )
        admin.post(
            prefix + "/files?kind=zip",
            headers=key(),
            files={"file": ("资料.zip", package, "application/zip")},
        )
    else:
        admin.post(
            prefix + "/files?kind=docx",
            headers=key(),
            files={"file": ("内容.docx", document("音频卡"), "application/octet-stream")},
        )
        admin.post(
            prefix + "/files?kind=audio",
            headers=key(),
            files={
                "file": ("完整音频." + extension, path.read_bytes(), "application/octet-stream")
            },
        )
    process_jobs(admin)
    restored = admin.get(prefix).json()
    audio = next(file for file in restored["files"] if file["kind"] == "audio")
    assert audio["state"] == "ready", audio
    assert len(restored["items"]) == 1
    metadata = admin.get(f"/api/admin/v1/media/{audio['media_id']}/status").json()
    assert metadata["playback_content_type"] == "audio/mpeg"
    assert (
        admin.get(f"/api/admin/v1/media/{audio['media_id']}").headers["content-type"]
        == "audio/mpeg"
    )


def test_aac_with_long_silence_uses_decoded_duration(admin, tmp_path):
    path = tmp_path / "silence.aac"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=30",
            "-af",
            "volume=0:enable='lt(t,15)'",
            "-codec:a",
            "aac",
            "-b:a",
            "128k",
            "-f",
            "adts",
            str(path),
        ],
        check=True,
    )
    upload = admin.post(
        "/api/admin/v1/media?kind=audio",
        headers=key(),
        files={"file": ("静音.AAC", path.read_bytes(), "audio/aac")},
    ).json()
    process_jobs(admin)
    metadata = admin.get(f"/api/admin/v1/media/{upload['id']}/status").json()
    assert metadata["state"] == "ready", metadata
    assert abs(metadata["duration"] - 30) < 0.25
    from juya_api.media_api import decoded_audio

    _, duration = decoded_audio(admin.get(f"/api/admin/v1/media/{upload['id']}").content)
    assert abs(duration - 30) < 0.25


def test_legacy_audio_requires_explicit_preparation_without_breaking_old_publication(
    system, admin, mini
):
    payload = content(admin)
    card = draft(admin, payload)
    published = publish(admin, card)
    with system["sessions"].begin() as db:
        medium = db.get(Media, payload["audio_id"])
        medium.playback_id = None
        medium.processing_stage = None
    ticket = mini.get(
        f"/api/mini/v1/cards/{card['id']}/media/{payload['audio_id']}/url?version_id={published['current_version_id']}"
    ).json()["url"]
    preview = admin.post(
        f"/api/admin/v1/cards/{card['id']}/preview", headers=key(), json={"revision": 1}
    )
    assert preview.status_code == 422
    assert "audio_playback_required" in preview.text
    before = admin.get(f"/api/admin/v1/media/{payload['audio_id']}/status").json()
    prepared = admin.post(f"/api/admin/v1/media/{payload['audio_id']}/retry", headers=key()).json()
    assert prepared["state"] == "processing"
    again = admin.post(f"/api/admin/v1/media/{payload['audio_id']}/retry", headers=key()).json()
    assert again["job_id"] == prepared["job_id"]
    assert mini.get(ticket).content == recording()
    process_jobs(admin)
    ready = admin.get(f"/api/admin/v1/media/{payload['audio_id']}/status").json()
    assert ready["state"] == "ready" and ready["playback_content_type"] == "audio/mpeg"
    assert ready["id"] == before["id"]
    assert mini.get(ticket).headers["content-type"] == "audio/mpeg"
    assert publish(admin, card)["current_version_id"] == published["current_version_id"]
