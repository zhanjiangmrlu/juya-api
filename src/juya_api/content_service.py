"""Publication invariants shared by both APIs, imports and background workers."""

import re
from datetime import timedelta

from sqlalchemy import func, select

from .content_contracts import SceneContent
from .content_models import Card, CardDraft, CardVersion, Media, Preview
from .database import timestamp
from .errors import DomainError
from .job_models import Job
from .models import Audit
from .security import fingerprint


def source_candidates(dialogue: list[dict], english: str) -> list[dict]:
    """Find full-word/phrase occurrences and return JavaScript-compatible UTF-16 ranges."""
    if not english.strip():
        return []
    expression = re.compile(r"(?<!\w)" + re.escape(english.strip()) + r"(?!\w)", re.I)
    matches = []
    for line in dialogue:
        text = line["english"]
        for match in expression.finditer(text):
            matches.append(
                {
                    "line_id": line["id"],
                    "start": len(text[: match.start()].encode("utf-16-le")) // 2,
                    "end": len(text[: match.end()].encode("utf-16-le")) // 2,
                    "quote": match.group(),
                    "sentence": text,
                }
            )
    return matches


def normalize(content: SceneContent) -> dict:
    """Drop empty optional chunks and bind only unambiguous vocabulary occurrences."""
    value = content.model_dump(mode="json")
    value["name"] = value["name"].strip()
    value["chunks"] = [c for c in value["chunks"] if c["english"].strip() or c["chinese"].strip()]
    for word in value["vocabulary"]:
        if word["source"] is None:
            candidates = source_candidates(value["dialogue"], word["english"])
            if len(candidates) == 1:
                word["source"] = {k: candidates[0][k] for k in ["line_id", "start", "end", "quote"]}
    return value


def validate_publication(db, content: dict) -> list[dict]:
    """Reject incomplete media, ambiguous sources and overlapping highlights at publication."""
    issues = []

    def issue(field, code, message):
        issues.append({"field": field, "code": code, "message": message})

    if not content["name"].strip():
        issue("name", "required", "请填写卡片名称")
    for field, kind in [("image_id", "image"), ("audio_id", "audio")]:
        medium = db.get(Media, content[field]) if content[field] else None
        if (
            not medium
            or medium.kind != kind
            or medium.owner_kind != "admin"
            or medium.state != "ready"
        ):
            issue(field, "media_required", "请上传已完成处理的场景图片或完整音频")
    if not content["dialogue"]:
        issue("dialogue", "required", "请至少填写一组完整对话")
    lines = {}
    for i, line in enumerate(content["dialogue"]):
        if line["id"] in lines:
            issue(f"dialogue.{i}", "duplicate_reference", "对话引用重复，请重新核对")
        lines[line["id"]] = line
        if not all(line[x].strip() for x in ["speaker", "english", "chinese"]):
            issue(f"dialogue.{i}", "required", "请补充人物、中英文对话")
    if not content["vocabulary"]:
        issue("vocabulary", "required", "请至少填写一条完整词汇")
    ranges: dict[str, list[tuple[int, int]]] = {}
    word_ids: set[str] = set()
    for i, word in enumerate(content["vocabulary"]):
        if word["id"] in word_ids:
            issue(f"vocabulary.{i}", "duplicate_reference", "词汇引用重复，请重新核对")
        word_ids.add(word["id"])
        if not word["english"].strip() or not word["meaning"].strip():
            issue(f"vocabulary.{i}", "required", "请填写词汇英文及本句释义")
        if word["pronunciation_issue"]:
            issue(f"vocabulary.{i}", "pronunciation_unconfirmed", "请先核对词汇读音")
        source = word["source"]
        valid = False
        if source and source["line_id"] in lines and source["end"] > source["start"]:
            text = lines[source["line_id"]]["english"]
            try:
                encoded = text.encode("utf-16-le")
                quote = encoded[source["start"] * 2 : source["end"] * 2].decode("utf-16-le")
                valid = (
                    bool(source["quote"])
                    and quote == source["quote"]
                    and source["end"] * 2 <= len(encoded)
                )
            except UnicodeDecodeError:
                valid = False
        if not valid:
            issue(f"vocabulary.{i}.source", "source_required", "请重新确认对应原句与高亮位置")
        elif source:
            occupied = ranges.setdefault(source["line_id"], [])
            if any(source["start"] < end and source["end"] > start for start, end in occupied):
                issue(f"vocabulary.{i}.source", "source_overlap", "高亮范围重叠，请重新核对")
            occupied.append((source["start"], source["end"]))
    for i, chunk in enumerate(content["chunks"]):
        if not chunk["english"].strip() or not chunk["chinese"].strip():
            issue(f"chunks.{i}", "required", "请补全语块中英文或删除该条")
    return issues


def require_card(db, card_id: str) -> Card:
    """A business-deleted card can never be revived by an old editor or import."""
    card = db.get(Card, card_id)
    if not card:
        raise DomainError(404, "card_missing", "未找到这张场景卡")
    if card.deleted_at:
        raise DomainError(410, "card_deleted", "这张场景卡已删除")
    return card


def published_card(db, card_id: str, version_id: str | None = None):
    """Authorize current content and media together, including on every ticket read."""
    card = require_card(db, card_id)
    if card.status != "published" or not card.current_version_id:
        raise DomainError(410, "card_offline", "这张场景卡已下线")
    if version_id and version_id != card.current_version_id:
        raise DomainError(409, "version_changed", "内容已更新，请刷新后继续")
    version = db.get(CardVersion, card.current_version_id)
    if not version or version.card_id != card.id:
        raise DomainError(503, "publication_unavailable", "场景资料暂不可用")
    return card, version


def revision_matches(draft: CardDraft | None, revision: int) -> CardDraft:
    """Reject stale writes instead of silently replacing a newer candidate."""
    if draft is None:
        raise DomainError(503, "draft_unavailable", "编辑资料暂不可用")
    if draft.revision != revision:
        raise DomainError(409, "revision_changed", "资料已变化，请刷新后核对")
    return draft


def card_view(db, card: Card) -> dict:
    draft = db.get(CardDraft, card.id)
    current = db.get(CardVersion, card.current_version_id) if card.current_version_id else None
    assert draft is not None
    display = current.payload if current and card.status != "draft" else draft.payload
    display_image = db.get(Media, display["image_id"]) if display["image_id"] else None
    return {
        "id": card.id,
        "display_name": display["name"],
        "display_thumbnail_id": display_image.thumbnail_id if display_image else None,
        "status": card.status,
        "current_version_id": card.current_version_id,
        "draft_revision": draft.revision,
        "content": draft.payload,
        "sort_order": card.sort_order,
        "updated_at": timestamp(draft.updated_at),
        "has_unpublished_changes": current is None
        or current.content_hash != fingerprint(draft.payload),
        "issues": validate_publication(db, draft.payload),
    }


def reviewed_candidate(db, card, admin_id, revision, preview_id, now):
    """Validate the exact saved review without publishing or replacing its content."""
    draft = db.get(CardDraft, card.id)
    assert draft is not None
    revision_matches(draft, revision)
    preview = db.get(Preview, preview_id)
    content_hash = fingerprint(draft.payload)
    if (
        not preview
        or preview.admin_id != admin_id
        or preview.card_id != card.id
        or preview.expires_at <= now
    ):
        raise DomainError(409, "preview_required", "请重新预览并确认发布")
    if preview.draft_revision != draft.revision or preview.content_hash != content_hash:
        raise DomainError(409, "preview_changed", "预览资料已变化，请重新核对")
    issues = validate_publication(db, draft.payload)
    if issues:
        raise DomainError(422, "publication_invalid", "请先补充发布资料", issues)
    return draft, content_hash


def publish_version(db, card: Card, admin_id: str, revision: int, preview_id: str, now):
    """Activate exactly the candidate that was previewed; keep old publications immutable."""
    draft, content_hash = reviewed_candidate(db, card, admin_id, revision, preview_id, now)
    current = db.get(CardVersion, card.current_version_id) if card.current_version_id else None
    if current and current.content_hash == content_hash:
        card.status = "published"
    else:
        number = (
            db.scalar(select(func.max(CardVersion.number)).where(CardVersion.card_id == card.id))
            or 0
        ) + 1
        version = CardVersion(
            card_id=card.id,
            number=number,
            payload=draft.payload,
            content_hash=content_hash,
            published_at=now,
        )
        db.add(version)
        db.flush()
        card.current_version_id, card.status = version.id, "published"
    db.add(Audit(admin_id=admin_id, action="card.publish", object_id=card.id, occurred_at=now))
    db.flush()
    return card_view(db, card)


def make_preview(db, card: Card, admin_id: str, revision: int, now):
    """Bind preview confirmation to the saved revision, content hash and administrator."""
    draft = db.get(CardDraft, card.id)
    assert draft is not None
    revision_matches(draft, revision)
    issues = validate_publication(db, draft.payload)
    if issues:
        raise DomainError(422, "publication_invalid", "请先补充发布资料", issues)
    preview = Preview(
        card_id=card.id,
        admin_id=admin_id,
        draft_revision=draft.revision,
        content_hash=fingerprint(draft.payload),
        expires_at=now + timedelta(minutes=30),
    )
    db.add(preview)
    db.flush()
    return {
        "preview_id": preview.id,
        "revision": draft.revision,
        "content": draft.payload,
        "expires_at": timestamp(preview.expires_at),
        "mode": "draft",
    }


def candidate_media_ready(db, content, admin_id):
    """A missing optional draft field is valid; an explicit unfinished/foreign reference is not."""
    for field, kind in [("image_id", "image"), ("audio_id", "audio")]:
        media_id = getattr(content, field)
        if not media_id:
            continue
        medium = db.get(Media, media_id)
        if (
            not medium
            or medium.owner_kind != "admin"
            or medium.owner_id != admin_id
            or medium.kind != kind
        ):
            raise DomainError(422, "media_invalid", "请选择已成功上传的场景素材")
        job = db.get(Job, medium.job_id) if medium.job_id else None
        if job and job.state == "failed":
            raise DomainError(422, "media_invalid", "素材处理失败，请更换或重新处理")
        if medium.state != "ready":
            raise DomainError(409, "media_processing", "请等待素材处理完成，再保存草稿")


def create_candidate(db, content, admin_id, now):
    """Create a new stable card and candidate using the same rules for manual/import entry."""
    candidate_media_ready(db, content, admin_id)
    card = Card(sort_order=(db.scalar(select(func.max(Card.sort_order))) or 0) + 1, created_at=now)
    db.add(card)
    db.flush()
    db.add(CardDraft(card_id=card.id, revision=1, payload=normalize(content), updated_at=now))
    db.add(Audit(admin_id=admin_id, action="card.create", object_id=card.id, occurred_at=now))
    db.flush()
    return card


def save_candidate(db, card_id, revision, content, admin_id, now):
    """An import update can only replace the explicitly confirmed current candidate."""
    card = require_card(db, card_id)
    draft = revision_matches(db.get(CardDraft, card.id), revision)
    candidate_media_ready(db, content, admin_id)
    draft.payload = normalize(content)
    draft.revision += 1
    draft.updated_at = now
    db.add(Audit(admin_id=admin_id, action="card.save", object_id=card.id, occurred_at=now))
    db.flush()
    return card
