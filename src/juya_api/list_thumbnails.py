"""Bounded, process-local small list derivatives; immutable stored media stay intact."""

import io
from collections import OrderedDict
from threading import Lock

from PIL import Image

from .content_models import Media
from .storage import ObjectStorage


class ListThumbnails:
    def __init__(self, capacity: int = 128):
        """Retain only a bounded number of small encoded results for this API instance."""
        self.capacity = capacity
        self.images: OrderedDict[tuple[str, str], bytes] = OrderedDict()
        self.lock = Lock()

    def read(self, medium: Media, storage: ObjectStorage) -> bytes:
        """Scale an already-authorized immutable thumbnail without storing or changing originals."""
        key = (medium.storage_key, medium.sha256)
        with self.lock:
            cached = self.images.pop(key, None)
            if cached is not None:
                self.images[key] = cached
                return cached
        with Image.open(io.BytesIO(storage.read(medium.storage_key))) as image:
            small = image.convert("RGB")
            small.thumbnail((144, 216), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            small.save(output, "WEBP", quality=60)
            result = output.getvalue()
        with self.lock:
            self.images.pop(key, None)
            self.images[key] = result
            if len(self.images) > self.capacity:
                self.images.popitem(last=False)
        return result
