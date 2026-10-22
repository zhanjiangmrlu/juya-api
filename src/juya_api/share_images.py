"""Bounded public display copies; each hit still verifies the private source bytes."""

import hashlib
import io
import warnings
from collections import OrderedDict
from threading import Lock

from PIL import Image, ImageOps

from .errors import DomainError

SHARE_DIMENSIONS = {"friends": (600, 480), "timeline": (600, 600)}
BACKGROUND = (255, 252, 245)
MAX_PIXELS = 20_000_000
MAX_COVER_BYTES = 1024 * 1024


def unavailable():
    return DomainError(503, "share_image_unavailable", "分享图片暂不可用，请重试")


class ShareImages:
    def __init__(
        self, *, capacity=32, max_cache_bytes=8 * 1024 * 1024, max_source_bytes=20 * 1024 * 1024
    ):
        self.capacity, self.max_cache_bytes = capacity, max_cache_bytes
        self.max_source_bytes = max_source_bytes
        self.images: OrderedDict[tuple[str, ...], bytes] = OrderedDict()
        self.cached_bytes = 0
        self.lock = Lock()

    def source(self, medium, storage):
        """Read at most expected size+1, so corrupted oversized objects remain bounded."""
        if not 0 < medium.size <= self.max_source_bytes:
            raise unavailable()
        stream = storage.stream(medium.storage_key, 0, medium.size)
        data = bytearray()
        try:
            for chunk in stream:
                data.extend(chunk[: medium.size + 1 - len(data)])
                if len(data) > medium.size:
                    break
        finally:
            stream.close()
        if len(data) != medium.size or hashlib.sha256(data).hexdigest() != medium.sha256:
            raise unavailable()
        return bytes(data)

    def prepare(self, card_id, version_id, medium, storage, variants):
        """Authorization happens in the route before both source verification and cache lookup."""
        try:
            source = self.source(medium, storage)
            keys = {
                variant: (card_id, version_id, medium.storage_key, medium.sha256, variant)
                for variant in variants
            }
            result = {}
            with self.lock:
                for variant, cache_key in keys.items():
                    cached = self.images.pop(cache_key, None)
                    if cached is not None:
                        self.images[cache_key] = cached
                        result[variant] = cached
            missing = [variant for variant in variants if variant not in result]
            if missing:
                rendered = self.render(source, missing)
                with self.lock:
                    for variant, encoded in rendered.items():
                        cache_key = keys[variant]
                        previous = self.images.pop(cache_key, None)
                        if previous is not None:
                            self.cached_bytes -= len(previous)
                        if len(encoded) <= self.max_cache_bytes and self.capacity > 0:
                            self.images[cache_key] = encoded
                            self.cached_bytes += len(encoded)
                        while self.images and (
                            len(self.images) > self.capacity
                            or self.cached_bytes > self.max_cache_bytes
                        ):
                            _, removed = self.images.popitem(last=False)
                            self.cached_bytes -= len(removed)
                result.update(rendered)
            return result
        except (
            DomainError,
            OSError,
            ValueError,
            SyntaxError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ):
            raise unavailable() from None

    def render(self, data, variants):
        """Keep all oriented pixels, flatten transparency and remove source metadata."""
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as original:
                if (
                    original.format not in {"PNG", "JPEG", "WEBP"}
                    or getattr(original, "n_frames", 1) != 1
                    or original.width * original.height > MAX_PIXELS
                ):
                    raise unavailable()
                original.verify()
            with Image.open(io.BytesIO(data)) as original:
                pixels = ImageOps.exif_transpose(original).convert("RGBA")
                result = {}
                for variant in variants:
                    size = SHARE_DIMENSIONS[variant]
                    contained = ImageOps.contain(pixels, size, Image.Resampling.LANCZOS)
                    canvas = Image.new("RGB", size, BACKGROUND)
                    canvas.paste(
                        contained,
                        ((size[0] - contained.width) // 2, (size[1] - contained.height) // 2),
                        contained.getchannel("A"),
                    )
                    output = io.BytesIO()
                    canvas.save(output, "JPEG", quality=85, optimize=True)
                    encoded = output.getvalue()
                    if len(encoded) > MAX_COVER_BYTES:
                        raise unavailable()
                    result[variant] = encoded
                return result
