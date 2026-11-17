"""Normalize new administrator content images before object storage writes."""

import io

from PIL import Image, ImageOps

from .errors import DomainError

IMAGE_COMPRESSION_THRESHOLD_BYTES = 1024 * 1024
IMAGE_WEBP_QUALITY = 90


def normalize_admin_image(data: bytes) -> bytes:
    """Encode data (the bounded source upload) as quality-90 WebP without resizing."""
    if len(data) <= IMAGE_COMPRESSION_THRESHOLD_BYTES:
        return data
    # Reuse the existing static-format, animation and 20MP validation before decoding pixels.
    from .media_api import decoded_image

    decoded_image(data)
    try:
        with Image.open(io.BytesIO(data)) as original:
            oriented = ImageOps.exif_transpose(original)
            image = oriented.convert(
                "RGBA" if "A" in oriented.getbands() or "transparency" in oriented.info else "RGB"
            )
        output = io.BytesIO()
        image.save(output, "WEBP", quality=IMAGE_WEBP_QUALITY, method=4)
        return output.getvalue()
    except (OSError, ValueError) as error:
        raise DomainError(422, "image_invalid", "图片压缩失败，请更换图片后重试") from error


def media_source_hash(medium) -> str | None:
    """Identify medium by original bytes while stored hashes continue to verify integrity."""
    if medium is None:
        return None
    return medium.source_sha256 or medium.sha256
