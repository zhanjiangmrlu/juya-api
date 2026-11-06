"""Independent PDF candidates/publications and one shared SQL/resource eligibility rule."""

import io
import logging

from sqlalchemy import exists, func, select

from .content_models import Card, CardStudyNoteVersion, Media
from .errors import DomainError


def decoded_pdf(data, limit):
    """Parse real page trees and content streams; a name or upload completion is insufficient."""
    from pypdf import PdfReader

    if not data or len(data) > limit:
        raise DomainError(422, "study_note_limit", "学习笔记为空或超过当前PDF大小限制")
    try:
        if not data.startswith(b"%PDF-"):
            raise ValueError("format")
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted and not reader.decrypt(""):
            raise ValueError("encrypted")
        if not reader.pages:
            raise ValueError("empty pages")
        for page in reader.pages:
            if page.get("/Type") != "/Page" or len(page.mediabox) != 4:
                raise ValueError("invalid page")
            contents = page.get_contents()
            if contents is not None:
                contents.get_data()
                # Parsing operations catches corrupt operators/stream syntax too.
                list(contents.operations)
    except Exception as error:
        logging.getLogger(__name__).debug("PDF validation rejected %s", type(error).__name__)
        raise DomainError(
            422, "study_note_invalid", "PDF格式无效、文件损坏或加密无法打开，请更换可读取的PDF"
        ) from None
    return {"content_type": "application/pdf", "processing_stage": "ready"}


def ready_pdf(db, media_id):
    """Recognize only validated administrator PDF objects, never nonempty references."""
    medium = db.get(Media, media_id) if media_id else None
    return (
        medium
        if (
            medium
            and medium.kind == "study_note"
            and medium.owner_kind == "admin"
            and medium.state == "ready"
            and medium.content_type == "application/pdf"
            and medium.size > 0
        )
        else None
    )


def published_note(db, card):
    """Resolve the same current publication used by discovery, detail and every ticket read."""
    version = (
        db.get(CardStudyNoteVersion, card.current_study_note_version_id)
        if card.current_study_note_version_id
        else None
    )
    return (
        version
        if version and version.card_id == card.id and ready_pdf(db, version.media_id)
        else None
    )


def note_filter():
    """Filter in SQL before counting/sorting/pagination; keep invalid/removed versions out."""
    return exists(
        select(CardStudyNoteVersion.id)
        .join(Media, Media.id == CardStudyNoteVersion.media_id)
        .where(
            CardStudyNoteVersion.id == Card.current_study_note_version_id,
            CardStudyNoteVersion.card_id == Card.id,
            Media.kind == "study_note",
            Media.owner_kind == "admin",
            Media.state == "ready",
            Media.content_type == "application/pdf",
            Media.size > 0,
        )
    )


def note_metadata(db, card):
    """Expose PDF metadata only after the caller has authorized the current card."""
    version = published_note(db, card)
    return (
        {
            "version_id": version.id,
            "media_id": version.media_id,
            "filename": version.filename,
            "size": version.size,
            "state": "ready",
        }
        if version
        else None
    )


def effective_media_id(db, selection, card=None):
    """A failed pending replacement keeps the previous valid editor attachment intact."""
    selection = selection or {"action": "keep"}
    if selection["action"] == "remove":
        return None
    if selection["action"] == "unresolved":
        return selection.get("previous_media_id")
    if selection["action"] == "set":
        if ready_pdf(db, selection.get("media_id")):
            return selection["media_id"]
        return selection.get("previous_media_id")
    note = published_note(db, card) if card else None
    return selection.get("media_id") or (note.media_id if note else None)


def change_selection(db, previous, change, admin_id, card=None):
    """Omitted changes preserve editor intent; explicit keep cancels a pending replacement."""
    if change is None:
        return previous
    if change.action == "set":
        medium = db.get(Media, change.media_id)
        if (
            not medium
            or medium.kind != "study_note"
            or medium.owner_kind != "admin"
            or medium.owner_id != admin_id
        ):
            raise DomainError(422, "study_note_media_invalid", "请选择当前管理员上传的学习笔记PDF")
        return {
            "action": "set",
            "media_id": medium.id,
            "previous_media_id": effective_media_id(db, previous, card),
            "candidate_file_ids": (previous or {}).get("candidate_file_ids", []),
        }
    if change.action == "keep":
        note = published_note(db, card) if card else None
        restored = (
            previous.get("previous_media_id")
            if previous and previous["action"] in {"set", "unresolved"}
            else effective_media_id(db, previous, card) or (note.media_id if note else None)
        )
        return {"action": "keep", "media_id": restored}
    return {
        "action": change.action,
        "previous_media_id": effective_media_id(db, previous, card)
        if change.action == "unresolved"
        else None,
        "candidate_file_ids": (previous or {}).get("candidate_file_ids", []),
    }


def note_issues(db, selection, card=None):
    """Unresolved/failed/pending candidates may be saved but cannot be published."""
    selection = selection or {"action": "keep"}
    if selection["action"] == "unresolved" or (
        selection["action"] == "set" and not ready_pdf(db, selection.get("media_id"))
    ):
        return [
            {
                "field": "study_note",
                "code": "study_note_not_ready",
                "message": "请处理学习笔记PDF，或明确移除后发布",
            }
        ]
    selected = effective_media_id(db, selection, card)
    if selected and not ready_pdf(db, selected):
        return [
            {
                "field": "study_note",
                "code": "study_note_not_ready",
                "message": "学习笔记PDF不可用，请更换或移除",
            }
        ]
    return []


def selection_view(db, selection, card=None):
    """Render effective/pending objects and provenance without mutating candidate revision."""
    from .import_models import ImportFile
    from .media_api import media_view
    from .zip_names import import_file_name

    selection = selection or {"action": "keep"}
    effective = ready_pdf(db, effective_media_id(db, selection, card))
    pending = (
        db.get(Media, selection.get("media_id"))
        if selection.get("media_id") and selection["action"] == "set"
        else None
    )
    candidates = []
    for file_id in selection.get("candidate_file_ids", []):
        row = db.get(ImportFile, file_id)
        if row:
            medium = db.get(Media, row.media_id) if row.media_id else None
            metadata = media_view(medium, db) if medium else None
            candidates.append(
                {
                    "file_id": row.id,
                    "name": import_file_name(db, row),
                    "size": row.size,
                    "media_id": row.media_id,
                    "state": metadata["state"] if metadata else "failed",
                    "error_code": row.error_code
                    or (metadata["error_code"] if metadata else "study_note_invalid"),
                    "parent_id": row.parent_id,
                }
            )
    return {
        "action": selection["action"],
        "attachment": media_view(effective, db) if effective else None,
        "pending_attachment": media_view(pending, db)
        if pending and (not effective or effective.id != pending.id)
        else None,
        "can_publish": not note_issues(db, selection, card),
        "candidates": candidates,
    }


def candidate_fingerprint(db, draft, card):
    """Bind preview to the PDF decision as well as body content, even when body is unchanged."""
    from .security import fingerprint

    return fingerprint(
        {
            "content": draft.payload,
            "study_note": draft.study_note,
            "effective_media_id": effective_media_id(db, draft.study_note, card),
        }
    )


def publish_note(db, card, draft, now):
    """Atomically activate an independent immutable version, including explicit removals."""
    media_id = effective_media_id(db, draft.study_note, card)
    existing = (
        db.get(CardStudyNoteVersion, card.current_study_note_version_id)
        if card.current_study_note_version_id
        else None
    )
    if (existing.media_id if existing else None) == media_id:
        return False
    medium = ready_pdf(db, media_id)
    from .media_api import media_view

    filename = media_view(medium, db)["original_name"] if medium else None
    number = (
        db.scalar(
            select(func.max(CardStudyNoteVersion.number)).where(
                CardStudyNoteVersion.card_id == card.id
            )
        )
        or 0
    ) + 1
    version = CardStudyNoteVersion(
        card_id=card.id,
        number=number,
        media_id=media_id,
        filename=filename,
        size=medium.size if medium else None,
        published_at=now,
    )
    db.add(version)
    db.flush()
    card.current_study_note_version_id = version.id
    # A published candidate becomes a stable baseline for subsequent omitted updates.
    draft.study_note = {"action": "keep", "media_id": media_id}
    return True


def require_note(db, card, media_id, version_id):
    """Reject stale PDF versions on GET, HEAD and Range even when the body is unchanged."""
    note = published_note(db, card)
    if not note or not version_id or note.id != version_id or note.media_id != media_id:
        raise DomainError(409, "study_note_changed", "学习笔记已更新或移除，请刷新后重新获取")
    return note
