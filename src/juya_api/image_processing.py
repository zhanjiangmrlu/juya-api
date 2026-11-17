"""Normalize new administrator content images before object storage writes."""

import io

from PIL import Image, ImageOps

from .errors import DomainError

IMAGE_TARGET_BYTES = 1024 * 1024


def normalize_admin_image(data: bytes) -> bytes:
    """Compress data (the bounded original upload) to WebP, never below quality 80."""
    if len(data) <= IMAGE_TARGET_BYTES:
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
        for quality in (85, 80):
            output = io.BytesIO()
            image.save(output, "WEBP", quality=quality, method=4)
            result = output.getvalue()
            if len(result) <= IMAGE_TARGET_BYTES:
                return result
        while image.size != (1, 1):
            factor = min(0.85, (IMAGE_TARGET_BYTES / len(result)) ** 0.5 * 0.95)
            image = image.resize(
                (max(1, int(image.width * factor)), max(1, int(image.height * factor))),
                Image.Resampling.LANCZOS,
            )
            output = io.BytesIO()
            image.save(output, "WEBP", quality=80, method=4)
            result = output.getvalue()
            if len(result) <= IMAGE_TARGET_BYTES:
                return result
    except (OSError, ValueError) as error:
        raise DomainError(422, "image_invalid", "图片压缩失败，请更换图片后重试") from error
    raise DomainError(422, "image_invalid", "图片无法压缩至1MB以内，请更换图片")


def media_source_hash(medium) -> str | None:
    """Identify medium by original bytes while stored hashes continue to verify integrity."""
    if medium is None:
        return None
    return medium.source_sha256 or medium.sha256
