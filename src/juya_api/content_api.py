"""Thin role-specific scene HTTP adapters over the same publication domain."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .content_contracts import CreateCard, PublishCard, Revision, SaveCard
from .content_models import Card, CardDraft, Media
from .content_service import (
    card_view,
    make_preview,
    normalize,
    publish_version,
    published_card,
    require_card,
    revision_matches,
)
from .database import timestamp
from .dependencies import administrator, database, learner, operation_key
from .models import Audit
from .transactions import operate


def admin_routes():
    router = APIRouter(prefix="/api/admin/v1", tags=["scene management"])

    @router.get("/cards")
    def listing(
        request: Request,
        status: str = "all",
        search: str = "",
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
        admin=Depends(administrator),
        db: Session = Depends(database),
    ):
        query = select(Card).join(CardDraft).where(Card.deleted_at.is_(None))
        if status in {"draft", "published", "offline"}:
            query = query.where(Card.status == status)
        if search.strip():
            query = query.where(
                CardDraft.payload["name"].as_string().contains(search.strip(), autoescape=True)
            )
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        rows = db.scalars(
            query.order_by(Card.sort_order, Card.id).offset((page - 1) * limit).limit(limit)
        ).all()
        return {
            "items": [card_view(db, card) for card in rows],
            "total": total,
            "page": page,
            "limit": limit,
        }

    @router.post("/cards", status_code=201)
    def create(
        body: CreateCard,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database),
    ):
        now = request.app.state.clock()

        def execute():
            card = Card(
                sort_order=(db.scalar(select(func.max(Card.sort_order))) or 0) + 1, created_at=now
            )
            db.add(card)
            db.flush()
            db.add(
                CardDraft(
                    card_id=card.id, revision=1, payload=normalize(body.content), updated_at=now
                )
            )
            db.add(
                Audit(admin_id=admin.id, action="card.create", object_id=card.id, occurred_at=now)
            )
            db.flush()
            return card_view(db, card)

        return operate(db, admin, "admin", key, "cards.create", body.model_dump(), now, execute)

    @router.get("/cards/{card_id}")
    def detail(card_id: str, admin=Depends(administrator), db: Session = Depends(database)):
        return card_view(db, require_card(db, card_id))

    @router.put("/cards/{card_id}")
    def save(
        card_id: str,
        body: SaveCard,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database),
    ):
        now = request.app.state.clock()

        def execute():
            card = require_card(db, card_id)
            draft = revision_matches(db.get(CardDraft, card.id), body.revision)
            draft.payload = normalize(body.content)
            draft.revision += 1
            draft.updated_at = now
            db.add(Audit(admin_id=admin.id, action="card.save", object_id=card.id, occurred_at=now))
            db.flush()
            return card_view(db, card)

        return operate(
            db, admin, "admin", key, f"cards.{card_id}.save", body.model_dump(), now, execute
        )

    @router.post("/cards/{card_id}/preview")
    def preview(
        card_id: str,
        body: Revision,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database),
    ):
        now = request.app.state.clock()
        return operate(
            db,
            admin,
            "admin",
            key,
            f"cards.{card_id}.preview",
            body.model_dump(),
            now,
            lambda: make_preview(db, require_card(db, card_id), admin.id, body.revision, now),
        )

    @router.post("/cards/{card_id}/publish")
    def publish(
        card_id: str,
        body: PublishCard,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database),
    ):
        now = request.app.state.clock()
        return operate(
            db,
            admin,
            "admin",
            key,
            f"cards.{card_id}.publish",
            body.model_dump(),
            now,
            lambda: publish_version(
                db, require_card(db, card_id), admin.id, body.revision, body.preview_id, now
            ),
        )

    @router.post("/cards/{card_id}/offline")
    def offline(
        card_id: str,
        body: Revision,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database),
    ):
        now = request.app.state.clock()

        def execute():
            card = require_card(db, card_id)
            revision_matches(db.get(CardDraft, card.id), body.revision)
            card.status = "offline"
            db.add(
                Audit(admin_id=admin.id, action="card.offline", object_id=card.id, occurred_at=now)
            )
            db.flush()
            return card_view(db, card)

        return operate(
            db, admin, "admin", key, f"cards.{card_id}.offline", body.model_dump(), now, execute
        )

    @router.delete("/cards/{card_id}")
    def delete(
        card_id: str,
        body: Revision,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database),
    ):
        now = request.app.state.clock()

        def execute():
            card = require_card(db, card_id)
            revision_matches(db.get(CardDraft, card.id), body.revision)
            card.deleted_at, card.status = now, "deleted"
            db.add(
                Audit(admin_id=admin.id, action="card.delete", object_id=card.id, occurred_at=now)
            )
            return {"id": card.id, "deleted": True}

        return operate(
            db, admin, "admin", key, f"cards.{card_id}.delete", body.model_dump(), now, execute
        )

    return router


def mini_routes():
    router = APIRouter(prefix="/api/mini/v1", tags=["published learning content"])

    @router.get("/cards")
    def listing(
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=50),
        user=Depends(learner),
        db: Session = Depends(database),
    ):
        query = select(Card).where(Card.status == "published", Card.deleted_at.is_(None))
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        rows = db.scalars(
            query.order_by(Card.sort_order, Card.id).offset((page - 1) * limit).limit(limit)
        ).all()
        items = []
        for card in rows:
            _, version = published_card(db, card.id)
            image = db.get(Media, version.payload["image_id"])
            items.append(
                {
                    "id": card.id,
                    "name": version.payload["name"],
                    "version_id": version.id,
                    "thumbnail_id": image.thumbnail_id if image else None,
                    "published_at": timestamp(version.published_at),
                }
            )
        return {"items": items, "total": total, "page": page, "limit": limit}

    @router.get("/cards/{card_id}")
    def detail(
        card_id: str,
        version_id: str | None = None,
        user=Depends(learner),
        db: Session = Depends(database),
    ):
        card, version = published_card(db, card_id, version_id)
        return {
            "card_id": card.id,
            "version_id": version.id,
            "content": version.payload,
            "published_at": timestamp(version.published_at),
        }

    return router
