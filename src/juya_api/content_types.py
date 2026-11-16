"""Explicit scene classification bound to immutable publication pointers."""

from sqlalchemy import exists, func, select

from .content_models import (
    Card,
    CardContentTypeVersion,
    CardDraft,
    CardStudyNoteVersion,
    CardVersion,
    SettingCounter,
)
from .errors import DomainError
from .security import fingerprint
from .study_notes import effective_media_id, note_filter, note_issues, published_note, ready_pdf


def enabled(db):
    setting = db.get(SettingCounter, "content_types_ready")
    return bool(setting and setting.value)


def type_issues(db, value, selection, card=None):
    if value is None:
        return [
            {
                "field": "content_type",
                "code": "content_type_required",
                "message": "请选择图解词汇或精读词汇",
            }
        ]
    selected = effective_media_id(db, selection, card)
    if value == "illustrated" and (selected or note_issues(db, selection, card)):
        return [
            {
                "field": "content_type",
                "code": "illustrated_pdf_conflict",
                "message": "图解词汇不能包含PDF，请改为精读或明确移除附件",
            }
        ]
    if value == "intensive" and not ready_pdf(db, selected):
        return [
            {
                "field": "content_type",
                "code": "intensive_pdf_required",
                "message": "精读词汇需要已校验可用的PDF",
            }
        ]
    return []


def bind(db, card, value, admin_id, now):
    old = (
        db.get(CardContentTypeVersion, card.current_content_type_version_id)
        if card.current_content_type_version_id
        else None
    )
    if old and (old.content_type, old.version_id, old.study_note_version_id, old.card_id) == (
        value,
        card.current_version_id,
        card.current_study_note_version_id,
        card.id,
    ):
        card.published_content_type = value
        return False
    number = (
        db.scalar(
            select(func.max(CardContentTypeVersion.number)).where(
                CardContentTypeVersion.card_id == card.id
            )
        )
        or 0
    )
    row = CardContentTypeVersion(
        card_id=card.id,
        number=number + 1,
        content_type=value,
        version_id=card.current_version_id,
        study_note_version_id=card.current_study_note_version_id,
        admin_id=admin_id,
        created_at=now,
    )
    db.add(row)
    db.flush()
    card.current_content_type_version_id, card.published_content_type = row.id, value
    return True


def published_query():
    return select(Card).where(Card.status == "published", Card.deleted_at.is_(None))


def invalid_card(db):
    record = CardContentTypeVersion
    matches = exists(
        select(record.id).where(
            record.id == Card.current_content_type_version_id,
            record.card_id == Card.id,
            record.content_type == Card.published_content_type,
            record.version_id == Card.current_version_id,
            record.study_note_version_id.is_not_distinct_from(Card.current_study_note_version_id),
        )
    )
    body = exists(
        select(CardVersion.id).where(
            CardVersion.id == Card.current_version_id, CardVersion.card_id == Card.id
        )
    )
    removed = exists(
        select(CardStudyNoteVersion.id).where(
            CardStudyNoteVersion.id == Card.current_study_note_version_id,
            CardStudyNoteVersion.card_id == Card.id,
            CardStudyNoteVersion.media_id.is_(None),
        )
    )
    pdf_ok = (
        (Card.published_content_type == "illustrated")
        & (Card.current_study_note_version_id.is_(None) | removed)
    ) | ((Card.published_content_type == "intensive") & note_filter())
    return db.scalar(published_query().where(~matches | ~body | ~pdf_ok).limit(1))


def ready(db, *, strict=False):
    if not enabled(db):
        return False
    if invalid_card(db):
        if strict:
            raise DomainError(
                503, "content_type_bindings_invalid", "发布分类绑定已变化，请管理员重新核对"
            )
        return False
    return True


def history_item(db, card):
    draft = db.get(CardDraft, card.id)
    version = db.get(CardVersion, card.current_version_id) if card.current_version_id else None
    note = (
        db.get(CardStudyNoteVersion, card.current_study_note_version_id)
        if card.current_study_note_version_id
        else None
    )
    pdf = published_note(db, card)
    warnings = []
    if not version or version.card_id != card.id:
        warnings.append("invalid_body")
    if card.current_study_note_version_id and (
        not note or note.card_id != card.id or (note.media_id and not pdf)
    ):
        warnings.append("invalid_pdf")
    if not pdf and draft and effective_media_id(db, draft.study_note, card):
        warnings.append("draft_pdf_only")
    record = (
        db.get(CardContentTypeVersion, card.current_content_type_version_id)
        if card.current_content_type_version_id
        else None
    )
    if record and (
        record.version_id != card.current_version_id
        or record.study_note_version_id != card.current_study_note_version_id
        or record.content_type != card.published_content_type
        or record.card_id != card.id
    ):
        warnings.append("binding_changed")
    value = {
        "card_id": card.id,
        "name": version.payload.get("name", "") if version else "",
        "current_version_id": card.current_version_id,
        "study_note_version_id": card.current_study_note_version_id,
        "draft_revision": draft.revision if draft else 0,
        "draft_content_type": draft.content_type if draft else None,
        "published_content_type": card.published_content_type,
        "suggestion": "intensive" if pdf else "illustrated",
        "warnings": warnings,
    }
    return {
        **value,
        "snapshot": fingerprint({**value, "binding": card.current_content_type_version_id}),
    }
