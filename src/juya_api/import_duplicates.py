"""Durable duplicate receipts, independent of live target availability."""

from typing import Literal

from pydantic import BaseModel

from .content_models import Card
from .import_models import ImportItem
from .listening_models import ListeningArticle, ListeningCandidate


class DuplicateDetail(BaseModel):
    candidate_id: str
    source_name: str
    source_path: str
    title_zh: str
    title_en: str
    reason: Literal["existing_content", "same_package", "cross_package"]
    target_kind: Literal[
        "scene_card", "scene_candidate", "listening_article", "listening_candidate", "unknown"
    ]
    target_id: str | None
    target_available: bool


class DuplicatePage(BaseModel):
    items: list[DuplicateDetail]
    total: int
    page: int
    limit: int
    total_pages: int


def receipt(candidate_id, source_name, path, title_zh, title_en, reason, kind, target_id):
    return {
        "candidate_id": candidate_id,
        "source_name": source_name,
        "source_path": path,
        "title_zh": title_zh,
        "title_en": title_en,
        "reason": reason,
        "target_kind": kind,
        "target_id": target_id,
    }


def render(db, batch, detail):
    model = {
        "scene_card": Card,
        "scene_candidate": ImportItem,
        "listening_article": ListeningArticle,
        "listening_candidate": ListeningCandidate,
    }.get(detail["target_kind"])
    target = db.get(model, detail["target_id"]) if model and detail["target_id"] else None
    available = bool(
        target and not getattr(target, "deleted_at", None) and not getattr(target, "removed", False)
    )
    if target and isinstance(target, (ImportItem, ListeningCandidate)):
        available = available and target.batch_id == batch.id
    return {**detail, "target_available": available}


def paged(db, batch, rows, page, limit):
    total = len(rows)
    pages = (total + limit - 1) // limit
    page = min(page, max(1, pages))
    return {
        "items": [render(db, batch, row) for row in rows[(page - 1) * limit : page * limit]],
        "total": total,
        "limit": limit,
        "page": page,
        "total_pages": pages,
    }
