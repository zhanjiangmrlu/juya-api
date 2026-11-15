"""Admin review of legacy classifications and explicit catalog activation."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import content_types as types
from .content_contracts import ContentType, SceneContent, Vocabulary
from .content_models import Card, CardDraft, SettingCounter
from .content_service import advance_catalog, catalog_lock, normalize
from .dependencies import administrator, database, operation_key, read_snapshot
from .errors import DomainError
from .listening_contracts import ListeningPayload, VocabularyWord
from .listening_vocabulary import resolve_vocabulary_sources
from .models import Audit
from .transactions import operate


class HistoryItem(BaseModel):
    card_id: str
    name: str
    current_version_id: str | None
    study_note_version_id: str | None
    draft_revision: int
    draft_content_type: ContentType | None
    published_content_type: ContentType | None
    suggestion: ContentType
    warnings: list[str]
    snapshot: str


class HistoryPage(BaseModel):
    items: list[HistoryItem]
    total: int
    page: int
    limit: int
    total_pages: int
    content_types_ready: bool


class HistorySelection(BaseModel):
    card_id: str = Field(min_length=1, max_length=36)
    snapshot: str = Field(min_length=64, max_length=64)
    content_type: ContentType


class Confirm(BaseModel):
    items: list[HistorySelection] = Field(min_length=1, max_length=100)


class Receipt(BaseModel):
    card_id: str
    status: str
    reason: str | None


class Confirmed(BaseModel):
    items: list[Receipt]


class Ready(BaseModel):
    content_types_ready: bool


class SceneMatchRequest(BaseModel):
    module: Literal["scene"]
    content: SceneContent


class ListeningMatchRequest(BaseModel):
    module: Literal["listening"]
    content: ListeningPayload


class SceneMatchResult(BaseModel):
    module: Literal["scene"]
    vocabulary: list[Vocabulary]


class ListeningMatchResult(BaseModel):
    module: Literal["listening"]
    vocabulary: list[VocabularyWord]


def vocabulary_routes():
    router = APIRouter(prefix="/api/admin/v1/vocabulary", tags=["scene management"])

    @router.post("/sources/preview", response_model=SceneMatchResult | ListeningMatchResult)
    def preview_sources(
        body: Annotated[SceneMatchRequest | ListeningMatchRequest, Field(discriminator="module")],
        admin=Depends(administrator),
    ):
        if isinstance(body, SceneMatchRequest):
            return {"module": "scene", "vocabulary": normalize(body.content)["vocabulary"]}
        content = body.content.model_dump(mode="json")
        resolve_vocabulary_sources(content)
        return {"module": "listening", "vocabulary": content["vocabulary"]}

    return router


def routes():
    router = APIRouter(prefix="/api/admin/v1/content-types", tags=["scene management"])

    @router.get("/history", response_model=HistoryPage, dependencies=[Depends(read_snapshot)])
    def history(
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
        unclassified_only: bool = False,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        query = types.published_query()
        if unclassified_only:
            query = query.where(Card.published_content_type.is_(None))
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        pages = (total + limit - 1) // limit
        page = min(page, max(1, pages))
        return {
            "items": [
                types.history_item(db, c)
                for c in db.scalars(query.order_by(Card.id).offset((page - 1) * limit).limit(limit))
            ],
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": pages,
            "content_types_ready": types.ready(db),
        }

    @router.post("/confirm", response_model=Confirmed)
    def confirm(
        body: Confirm,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        now = request.app.state.clock()

        def execute():
            catalog_lock(db)
            items = []
            for choice in body.items:
                card = db.get(Card, choice.card_id)
                view = (
                    types.history_item(db, card)
                    if card and not card.deleted_at and card.status == "published"
                    else None
                )
                reason = None
                if not view or view["snapshot"] != choice.snapshot:
                    reason = "snapshot_changed"
                elif {"invalid_body", "invalid_pdf"}.intersection(view["warnings"]) or view[
                    "suggestion"
                ] != choice.content_type:
                    reason = "type_pdf_conflict"
                else:
                    assert card is not None
                    types.bind(db, card, choice.content_type, admin.id, now)
                    draft = db.get(CardDraft, card.id)
                    if draft and not draft.content_type:
                        draft.content_type = choice.content_type
                        draft.revision += 1
                        draft.updated_at = now
                    db.add(
                        Audit(
                            admin_id=admin.id,
                            action="card.type.confirm",
                            object_id=card.id,
                            occurred_at=now,
                        )
                    )
                    advance_catalog(db)
                    db.flush()
                items.append(
                    {
                        "card_id": choice.card_id,
                        "status": "skipped" if reason else "confirmed",
                        "reason": reason,
                    }
                )
            return {"items": items}

        return operate(
            db, admin, "admin", key, "content_types.confirm", body.model_dump(), now, execute
        )

    @router.post("/enable", response_model=Ready)
    def enable(
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        now = request.app.state.clock()

        def execute():
            catalog_lock(db)
            if types.invalid_card(db):
                raise DomainError(
                    409, "content_type_bindings_invalid", "仍有未归类或正文、附件不一致的发布卡片"
                )
            db.merge(SettingCounter(name="content_types_ready", value=1))
            db.add(
                Audit(
                    admin_id=admin.id,
                    action="card.type.enable",
                    object_id="catalog",
                    occurred_at=now,
                )
            )
            return {"content_types_ready": True}

        return operate(db, admin, "admin", key, "content_types.enable", {}, now, execute)

    return router
