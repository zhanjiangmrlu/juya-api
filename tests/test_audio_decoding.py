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


def test_streamed_pcm_wav_with_unknown_riff_and_data_lengths_uses_actual_complete_frames():
    data = bytearray(recording())
    data[4:8] = b"\xff" * 4
    offset = data.index(b"data") + 4
    data[offset : offset + 4] = b"\xff" * 4
    assert decoded_audio(bytes(data)) == ("audio/wav", 1.0)


def test_unknown_length_pcm_wav_still_rejects_an_incomplete_sample_frame():
    data = bytearray(recording())
    data[4:8] = b"\xff" * 4
    offset = data.index(b"data") + 4
    data[offset : offset + 4] = b"\xff" * 4
    with pytest.raises(DomainError, match="audio_invalid"):
        decoded_audio(bytes(data[:-1]))
