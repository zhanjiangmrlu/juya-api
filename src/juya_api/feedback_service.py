"""Feedback transactions, safe summaries and private screenshot authorization."""

import io
import json
import warnings
from datetime import UTC, timedelta

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import and_, func, select

from .content_models import Card, CardVersion
from .database import timestamp
from .errors import DomainError
from .feedback_models import Feedback, FeedbackEvent, FeedbackImage, FeedbackRead
from .models import Audit
from .pronunciation_api import session_digest
from .security import decrypt, encrypt


def owned_feedback(db, feedback_id, actor, role, *, lock=False):
    query = select(Feedback).where(Feedback.id == feedback_id)
    if role == "mini":
        query = query.where(Feedback.user_id == actor.id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        raise DomainError(404, "feedback_missing", "未找到这条反馈")
    return row


def unread_query(actor, role):
    query = (
        select(Feedback)
        .outerjoin(
            FeedbackRead,
            and_(
                FeedbackRead.feedback_id == Feedback.id,
                FeedbackRead.role == role,
                FeedbackRead.actor_id == actor.id,
            ),
        )
        .where(
            (Feedback.latest_admin_event_id if role == "mini" else Feedback.latest_user_event_id)
            > func.coalesce(FeedbackRead.event_id, 0)
        )
    )
    return query.where(Feedback.user_id == actor.id) if role == "mini" else query


def is_unread(db, row, actor, role):
    cursor = db.get(FeedbackRead, (row.id, role, actor.id))
    latest = row.latest_admin_event_id if role == "mini" else row.latest_user_event_id
    return latest > (cursor.event_id if cursor else 0)


def authorized_image(db, image_id, actor, role):
    image = db.get(FeedbackImage, image_id)
    if (
        not image
        or (role == "mini" and image.user_id != actor.id)
        or (role == "admin" and not image.feedback_id)
    ):
        raise DomainError(404, "feedback_image_missing", "未找到可查看的反馈截图")
    if image.feedback_id:
        thread = owned_feedback(db, image.feedback_id, actor, role)
        if thread.user_id != image.user_id or not db.get(
            FeedbackEvent, (thread.id, image.event_id)
        ):
            raise DomainError(404, "feedback_image_missing", "反馈截图暂不可用")
    return image


def image_view(image, request, actor, role):
    expires = request.app.state.clock() + timedelta(minutes=5)
    payload = {
        "purpose": "feedback-image",
        "role": role,
        "actor": actor.id,
        "session": session_digest(request, role),
        "image_id": image.id,
        "expires": int(expires.replace(tzinfo=UTC).timestamp()),
    }
    grant = encrypt(request.app.state.settings, json.dumps(payload))
    return {
        "id": image.id,
        "state": "ready",
        "url": f"/api/{role}/v1/feedback/images/{grant}",
        "content_type": image.content_type,
        "width": image.width,
        "height": image.height,
        "size": image.size,
    }


def feedback_view(db, row, request, actor, role, *, detail=False):
    # READ COMMITTED may observe a later append in each following SELECT. Keep
    # the timeline and private attachments at the header's captured watermark.
    latest_event_id = row.latest_event_id
    unread = is_unread(db, row, actor, role)
    settings = request.app.state.settings
    card = db.get(Card, row.card_id) if row.card_id else None
    version = (
        db.get(CardVersion, card.current_version_id) if card and card.current_version_id else None
    )
    available = bool(
        card
        and not card.deleted_at
        and card.status == "published"
        and version
        and version.card_id == card.id
    )
    reason = (
        None
        if not row.card_id or available
        else ("deleted" if not card or card.deleted_at else "offline")
    )
    events = []
    if detail:
        images: dict[int, list] = {}
        for image in db.scalars(
            select(FeedbackImage)
            .where(
                FeedbackImage.feedback_id == row.id,
                FeedbackImage.event_id <= latest_event_id,
            )
            .order_by(FeedbackImage.event_id, FeedbackImage.event_position, FeedbackImage.id)
        ):
            images.setdefault(image.event_id, []).append(image_view(image, request, actor, role))
        for event in db.scalars(
            select(FeedbackEvent)
            .where(FeedbackEvent.feedback_id == row.id, FeedbackEvent.id <= latest_event_id)
            .order_by(FeedbackEvent.id)
        ):
            events.append(
                {
                    "id": event.id,
                    "actor": event.actor,
                    "text": decrypt(settings, event.text_cipher),
                    "status": event.status,
                    "images": images.get(event.id, []),
                    "created_at": timestamp(event.created_at),
                }
            )
    return {
        "id": row.id,
        "user_id": row.user_id,
        "category": row.category,
        "status": row.status,
        "summary": decrypt(settings, row.summary_cipher),
        "source": row.source,
        "card_id": row.card_id,
        "version_id": row.version_id,
        "source_title": row.source_title,
        "source_title_en": row.source_title_en,
        "source_available": available,
        "source_unavailable_reason": reason,
        "created_at": timestamp(row.created_at),
        "updated_at": timestamp(row.updated_at),
        "unread": unread,
        "latest_event_id": latest_event_id,
        "events": events,
    }


def check_images(db, user_id, ids, *, lock=False):
    if not ids:
        return []
    query = select(FeedbackImage).where(FeedbackImage.id.in_(ids))
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    rows = list(db.scalars(query))
    if len(rows) != len(ids) or any(
        row.user_id != user_id or row.feedback_id is not None for row in rows
    ):
        raise DomainError(422, "feedback_image_invalid", "请选择本人已成功上传且尚未提交的截图")
    indexed = {row.id: row for row in rows}
    return [indexed[image_id] for image_id in ids]


def append_event(db, settings, row, actor, role, text, status, image_ids, now):
    """Caller holds actor and feedback locks, giving accepted operations one stable order."""
    images = check_images(db, row.user_id, image_ids, lock=True)
    now = max(now, row.updated_at)
    row.latest_event_id += 1
    if status is not None:
        row.status = status
    row.updated_at = now
    event = FeedbackEvent(
        feedback_id=row.id,
        id=row.latest_event_id,
        actor="user" if role == "mini" else "admin",
        actor_id=actor.id,
        text_cipher=encrypt(settings, text) if text else None,
        status=status,
        created_at=now,
    )
    db.add(event)
    db.flush()
    for position, image in enumerate(images):
        image.feedback_id, image.event_id = row.id, event.id
        image.event_position = position
    if role == "mini":
        row.latest_user_event_id = event.id
    elif text:
        row.latest_admin_event_id = event.id
    db.flush()
    return event


def audit(db, actor, action, object_id, now):
    db.add(Audit(admin_id=actor.id, action=action, object_id=object_id, occurred_at=now))


def normalized_image(data):
    """Decode static pixels, orient, strip metadata and compress the actual saved screenshot."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as original:
                if (
                    original.format not in {"PNG", "JPEG", "WEBP"}
                    or getattr(original, "n_frames", 1) != 1
                    or original.width * original.height > 20_000_000
                ):
                    raise ValueError("invalid screenshot")
                original.verify()
            with Image.open(io.BytesIO(data)) as original:
                pixels = ImageOps.exif_transpose(original).convert("RGBA")
                pixels.thumbnail((2048, 2048))
                clean = Image.new("RGB", pixels.size, "white")
                clean.paste(pixels, mask=pixels.getchannel("A"))
                output = io.BytesIO()
                clean.save(output, format="JPEG", quality=85, optimize=True)
                return output.getvalue(), clean.width, clean.height
    except (
        ValueError,
        OSError,
        UnidentifiedImageError,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ):
        raise DomainError(
            422, "image_invalid", "图片无法读取，请选择静态PNG、JPEG或WebP图片"
        ) from None
