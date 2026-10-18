"""Bounded, offline normalization of validated originals to complete MP3 playback."""

import shutil
import subprocess
import tempfile
from pathlib import Path

from .errors import DomainError
from .media_api import bounded_wave_input, decoded_audio


def playback_mp3(data: bytes, content_type: str, duration: float, limit: int) -> bytes:
    """Reuse verified MP3 or transcode without network, metadata or per-speed variants."""
    if content_type == "audio/mpeg":
        return data
    executable = shutil.which("ffmpeg")
    if not executable:
        raise DomainError(503, "audio_conversion_unavailable", "音频转换暂不可用，请稍后重试")
    demuxer = {"audio/wav": "wav", "audio/mp4": "mov", "audio/aac": "aac"}[content_type]
    with tempfile.TemporaryDirectory(prefix="juya-playback-") as directory:
        source, target = Path(directory) / "source", Path(directory) / "playback.mp3"
        source.write_bytes(bounded_wave_input(data) if content_type == "audio/wav" else data)
        try:
            subprocess.run(
                [
                    executable,
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
                    str(source),
                    "-map",
                    "0:a:0",
                    "-vn",
                    "-sn",
                    "-dn",
                    "-map_metadata",
                    "-1",
                    "-codec:a",
                    "libmp3lame",
                    "-b:a",
                    "128k",
                    "-ar",
                    "44100",
                    "-id3v2_version",
                    "3",
                    "-fs",
                    str(limit + 1),
                    str(target),
                ],
                capture_output=True,
                timeout=60,
                check=True,
            )
            if not target.exists() or not 0 < target.stat().st_size <= limit:
                raise ValueError("invalid output size")
            output = target.read_bytes()
            actual_type, actual_duration = decoded_audio(output)
            if actual_type != "audio/mpeg" or abs(actual_duration - duration) > max(
                0.25, duration * 0.005
            ):
                raise ValueError("incomplete converted audio")
            return output
        except (ValueError, OSError, subprocess.SubprocessError, DomainError):
            raise DomainError(
                422, "audio_conversion_failed", "音频兼容处理未通过完整性校验，请重试或更换文件"
            ) from None
