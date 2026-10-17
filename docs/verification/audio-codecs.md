# Full audio decoding evidence

2026-10-17, isolated ECS verification container, network disabled, read-only source mount, 256MB memory, 0.5 CPU, temporary scratch directory only. No database or account configuration was mounted.

New `juya_api.media_api.decoded_audio` code was mounted into a cached Python3.13.13 image solely to exercise its installed FFmpeg/FFprobe binaries. That legacy image is not the new production runtime.

| Actual input | Reported MIME | Duration | Bytes |
| --- | --- | --- | --- |
| Tencent-generated MP3 | audio/mpeg | 2.628s | 10,512 |
| WAV dialogue fixture | audio/wav | 2.650s | 84,844 |
| M4A encoded from WAV | audio/mp4 | 2.650s | 17,970 |
| ADTS AAC encoded from WAV | audio/aac | 2.752s | 17,293 |

All four passed. Truncating the WAV by100 bytes was rejected as `audio_invalid`.

The PCM path validates the complete declared frame payload. Compressed inputs use an explicitly selected allowed demuxer, file/pipe protocol restriction, metadata validation and full FFmpeg decode under a60-second deadline. A successful metadata probe alone is insufficient. Unit regressions reproduced truncated PCM acceptance, metadata success followed by decode failure, and playlist input before the change; all now reject. Latest local suite95 passed/7 external-only skips, Ruff and mypy passed.

This confirms decoder behavior on Linux, not the pending new production image, WeChat device playback, complete speech quality or mixed learning load acceptance.
