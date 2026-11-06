"""Independent PDF candidates/publications and one shared SQL/resource eligibility rule."""

import io
import logging

from sqlalchemy import exists, func, select

from .content_models import Card, CardStudyNoteVersion, Media
from .errors import DomainError

PDF_ERROR_MESSAGES = {
    "study_note_format_invalid": "文件实际格式不是PDF，请选择PDF文件",
    "study_note_invalid": "PDF文件结构损坏或内容无法读取，请更换完整PDF",
    "study_note_encrypted": "PDF已加密且无法打开，请解除密码保护后重新上传",
    "study_note_empty": "PDF文件为空，请重新选择",
    "study_note_limit": "PDF文件超过当前大小限制，请压缩或更换文件",
}


def decoded_pdf(data, limit):
    """Parse actual pages/content and report safe, distinct rejection reasons."""
    from pypdf import PdfReader
    from pypdf.errors import FileNotDecryptedError, WrongPasswordError

    def reject(code):
        raise DomainError(422, code, PDF_ERROR_MESSAGES[code])

    if not data:
        reject("study_note_empty")
    if len(data) > limit:
        reject("study_note_limit")
    if not data.startswith(b"%PDF-"):
        reject("study_note_format_invalid")
    try:
        try:
            reader = PdfReader(io.BytesIO(data), strict=True)
        except NotImplementedError as error:
            # Security-handler rejection can happen before a reader instance is returned.
            trace = error.__traceback__
            while trace is not None:
                if trace.tb_frame.f_globals.get("__name__") == "pypdf._encryption":
                    reject("study_note_encrypted")
                trace = trace.tb_next
            raise
        if reader.is_encrypted:
            try:
                decrypted = reader.decrypt("")
            except Exception:
                reject("study_note_encrypted")
            if not decrypted:
                reject("study_note_encrypted")
        if not reader.pages:
            raise ValueError("empty pages")
        for page in reader.pages:
            if page.get("/Type") != "/Page" or len(page.mediabox) != 4:
                raise ValueError("invalid page")
            contents = page.get_contents()
            if contents is not None:
                contents.get_data()
                list(contents.operations)
    except DomainError:
        raise
    except (FileNotDecryptedError, WrongPasswordError):
        reject("study_note_encrypted")
    except Exception as error:
        logging.getLogger(__name__).debug("PDF validation rejected %s", type(error).__name__)
        reject("study_note_invalid")
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
    if "previous_media_id" in change.model_fields_set:
        fallback = ready_pdf(db, change.previous_media_id)
        if not fallback or fallback.owner_id != admin_id:
            raise DomainError(
                422, "study_note_previous_invalid", "请选择当前管理员已校验可用的PDF作为保留附件"
            )
    if change.action == "set":
        medium = db.get(Media, change.media_id)
        if (
            not medium
            or medium.kind != "study_note"
            or medium.owner_kind != "admin"
            or medium.owner_id != admin_id
        ):
            raise DomainError(422, "study_note_media_invalid", "请选择当前管理员上传的学习笔记PDF")
    return project_selection(db, previous, change.model_dump(), card)


def project_selection(db, previous, change, card=None):
    """Project a staged change onto the target draft without changing either source."""
    if change is None:
        return previous
    action = change["action"]
    fallback_id = change.get("previous_media_id") or effective_media_id(db, previous, card)
    if action == "set":
        return {
            "action": "set",
            "media_id": change["media_id"],
            "previous_media_id": fallback_id,
            "candidate_file_ids": (previous or {}).get("candidate_file_ids", []),
        }
    if action == "keep":
        note = published_note(db, card) if card else None
        restored = (
            previous.get("previous_media_id")
            if previous and previous["action"] in {"set", "unresolved"}
            else effective_media_id(db, previous, card) or (note.media_id if note else None)
        )
        return {"action": "keep", "media_id": restored}
    return {
        "action": action,
        "previous_media_id": fallback_id if action == "unresolved" else None,
        "candidate_file_ids": (previous or {}).get("candidate_file_ids", []),
    }


def note_issues(db, selection, card=None):
    """Unresolved/failed/pending candidates may be saved but cannot be published."""
    selection = selection or {"action": "keep"}
    if selection["action"] == "unresolved" or (
        selection["action"] == "set" and not ready_pdf(db, selection.get("media_id"))
    ):
        from .job_models import Job

        medium = db.get(Media, selection.get("media_id")) if selection.get("media_id") else None
        job = db.get(Job, medium.job_id) if medium and medium.job_id else None
        message = PDF_ERROR_MESSAGES.get(job.error_code) if job and job.state == "failed" else None
        candidates = selection.get("candidate_file_ids", [])
        if not message and selection["action"] == "unresolved" and len(candidates) == 1:
            from .import_models import ImportFile
            from .import_service import file_view

            source = db.get(ImportFile, candidates[0])
            message = file_view(db, source)["error"] if source else None
        return [
            {
                "field": "study_note",
                "code": "study_note_not_ready",
                "message": message or "请处理学习笔记PDF，或明确移除后发布",
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


def selection_view(db, selection, card=None, *, candidate_file_ids=None):
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
    if candidate_file_ids is None:
        candidate_file_ids = selection.get("candidate_file_ids", [])
    for file_id in candidate_file_ids:
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
                    "error": PDF_ERROR_MESSAGES.get(row.error_code)
                    or (metadata["error"] if metadata else None),
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
