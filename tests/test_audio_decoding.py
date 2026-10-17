"""Successful metadata probing cannot substitute for decoding all uploaded audio frames."""

import json
import subprocess

import pytest

from juya_api.errors import DomainError
from juya_api.media_api import decoded_audio

from .content_helpers import recording


def test_pcm_with_truncated_frames_is_rejected_even_when_its_header_declares_valid_duration():
    with pytest.raises(DomainError, match="audio_invalid"):
        decoded_audio(recording()[:-100])


def test_probe_success_is_rejected_when_actual_full_decoding_fails(monkeypatch):
    monkeypatch.setattr("juya_api.media_api.shutil.which", lambda name: "/decoder/" + name)

    def run(command, **options):
        if command[0].endswith("ffprobe"):
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps(
                    {
                        "format": {"duration": "2", "format_name": "mp3"},
                        "streams": [{"codec_type": "audio"}],
                    }
                ).encode(),
            )
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr("juya_api.media_api.subprocess.run", run)
    with pytest.raises(DomainError, match="audio_invalid"):
        decoded_audio(b"ID3" + b"corrupt frames")


def test_playlist_content_is_rejected_before_any_external_decoder_is_invoked(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("A playlist must never be opened as uploaded audio")

    monkeypatch.setattr("juya_api.media_api.subprocess.run", forbidden)
    with pytest.raises(DomainError, match="audio_invalid"):
        decoded_audio(b"#EXTM3U\nhttps://not-an-audio-file.invalid/private\n")
