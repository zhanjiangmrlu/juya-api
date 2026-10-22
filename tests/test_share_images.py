"""Image processing budgets and the actual pixels of public display-only copies."""

import hashlib
import io
from types import SimpleNamespace

import pytest
from PIL import Image


def source(tmp_path, image, *, animated=False):
    from juya_api.storage import ObjectStorage

    output = io.BytesIO()
    image.save(
        output,
        "PNG",
        **(
            {"save_all": True, "append_images": [Image.new("RGBA", image.size, "blue")]}
            if animated
            else {}
        ),
    )
    data = output.getvalue()
    storage = ObjectStorage(SimpleNamespace(storage_backend="local", media_root=tmp_path))
    storage.put("source.png", data, "image/png")
    medium = SimpleNamespace(
        storage_key="source.png", size=len(data), sha256=hashlib.sha256(data).hexdigest()
    )
    return storage, medium


def test_transparent_pixels_are_composited_on_a_clean_light_canvas(tmp_path):
    from juya_api.share_images import ShareImages

    pixels = Image.new("RGBA", (40, 80), (255, 0, 0, 0))
    pixels.paste("blue", (10, 20, 30, 60))
    storage, medium = source(tmp_path, pixels)
    result = ShareImages().prepare("card", "version", medium, storage, ["friends", "timeline"])
    for variant, center_y in [("friends", 240), ("timeline", 300)]:
        image = Image.open(io.BytesIO(result[variant]))
        assert min(image.getpixel((300, 10))) > 235
        red, green, blue = image.getpixel((300, center_y))
        assert blue > 220 and max(red, green) < 35
        assert not image.getexif()


@pytest.mark.parametrize("kind", ["animation", "pixels"])
def test_animation_and_more_than_twenty_megapixels_are_unshareable(tmp_path, kind):
    from juya_api.errors import DomainError
    from juya_api.share_images import ShareImages

    pixels = (
        Image.new("RGBA", (20, 30), "red")
        if kind == "animation"
        else Image.new("1", (20_000_001, 1), 1)
    )
    storage, medium = source(tmp_path, pixels, animated=kind == "animation")
    with pytest.raises(DomainError) as failure:
        ShareImages().prepare("card", "version", medium, storage, ["friends"])
    assert failure.value.status == 503


def test_source_byte_budget_rejects_before_io_and_oversize_reads_stop_immediately():
    from juya_api.errors import DomainError
    from juya_api.share_images import ShareImages

    medium = SimpleNamespace(storage_key="source", size=11, sha256="unused")

    class NoRead:
        def stream(self, *_):
            raise AssertionError("Source exceeding the configured byte budget was read")

    with pytest.raises(DomainError):
        ShareImages(max_source_bytes=10).prepare("c", "v", medium, NoRead(), ["friends"])

    class Oversize:
        def stream(self, *_):
            yield b"x" * 12
            raise AssertionError("Oversized source stream was consumed beyond size+1")

    with pytest.raises(DomainError) as failure:
        ShareImages().prepare("c", "v", medium, Oversize(), ["friends"])
    assert failure.value.code == "share_image_unavailable"


def test_encoded_cache_obeys_entry_and_total_byte_budgets_without_disabling_shares(tmp_path):
    from juya_api.share_images import ShareImages

    storage, medium = source(tmp_path, Image.new("RGB", (40, 80), "blue"))
    cache = ShareImages(capacity=1)
    result = cache.prepare("c", "v", medium, storage, ["friends", "timeline"])
    assert len(result) == 2 and len(cache.images) == 1
    assert cache.cached_bytes == sum(len(encoded) for encoded in cache.images.values())
    tiny = ShareImages(max_cache_bytes=1)
    result = tiny.prepare("c", "v", medium, storage, ["friends", "timeline"])
    assert all(result.values()) and not tiny.images and tiny.cached_bytes == 0
