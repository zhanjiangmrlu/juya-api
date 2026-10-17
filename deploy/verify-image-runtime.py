"""Run inside each built image with no network, credentials or database."""

import json
import os
import platform
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

from juya_api.errors import DomainError
from juya_api.media_api import decoded_audio


def main():
    assert sys.version_info[:2] == (3, 13)
    assert platform.machine() == "x86_64"
    assert os.getuid() == 10001
    assert sys.argv[1] in ("admin", "mini")
    assert os.environ["JUYA_IMAGE_ROLE"] == sys.argv[1]
    results = []
    with tempfile.TemporaryDirectory(prefix="juya-image-") as folder:
        source = Path(folder) / "sample.wav"
        with wave.open(str(source), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b"\x00\x00" * 16000)
        for extension, codec in [
            ("wav", None),
            ("mp3", "libmp3lame"),
            ("m4a", "aac"),
            ("aac", "aac"),
        ]:
            target = source if extension == "wav" else Path(folder) / ("sample." + extension)
            if codec:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-nostdin",
                        "-v",
                        "error",
                        "-threads",
                        "1",
                        "-i",
                        str(source),
                        "-c:a",
                        codec,
                        str(target),
                    ],
                    capture_output=True,
                    check=True,
                    timeout=30,
                )
            content_type, duration = decoded_audio(target.read_bytes())
            assert 0.9 <= duration <= 1.5
            results.append({"format": extension, "content_type": content_type})
        try:
            decoded_audio(source.read_bytes()[:-100])
        except DomainError as error:
            assert error.code == "audio_invalid"
        else:
            raise AssertionError("truncated audio accepted")
    print(
        json.dumps(
            {
                "role": sys.argv[1],
                "uid": os.getuid(),
                "python": platform.python_version(),
                "formats": results,
            }
        )
    )


if __name__ == "__main__":
    main()
