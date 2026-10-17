"""Thin role-specific scene HTTP adapters over the same publication domain."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .content_contracts import CreateCard, PublishCard, Revision, SaveCard
from .content_models import Card, CardDraft, CardVersion, Media
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
from .learning_models import Completion, DailyLearning, Favorite
from .learning_service import business_date, card_state
from .models import Audit
from .response_contracts import (
    CardBrief,
    CardPreview,
    CardView,
    DeletedCard,
    Page,
    PublishedDetail,
    PublishedPreview,
)
from .transactions import operate


def admin_routes():
    router = APIRouter(prefix="/api/admin/v1", tags=["scene management"])

    @router.get("/cards", response_model=Page[CardView])
    def listing(
        request: Request,
        status: str = "all",
        search: str = "",
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
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

    @router.post("/cards", status_code=201, response_model=CardView)
    def create(
        body: CreateCard,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
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

        return operate(
            db,
            admin,
            "admin",
            key,
            "cards.create",
            body.model_dump(exclude_unset=True),
            now,
            execute,
        )

    @router.get("/cards/{card_id}", response_model=CardView)
    def detail(
        card_id: str,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        return card_view(db, require_card(db, card_id))

    @router.get("/cards/{card_id}/published", response_model=PublishedPreview)
    def published_preview(
        card_id: str,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        card, version = published_card(db, card_id)
        return {
            "card_id": card.id,
            "version_id": version.id,
            "content": version.payload,
            "mode": "published",
        }

    @router.put("/cards/{card_id}", response_model=CardView)
    def save(
        card_id: str,
        body: SaveCard,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
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
            db,
            admin,
            "admin",
            key,
            f"cards.{card_id}.save",
            body.model_dump(exclude_unset=True),
            now,
            execute,
        )

    @router.post("/cards/{card_id}/preview", response_model=CardPreview)
    def preview(
        card_id: str,
        body: Revision,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        now = request.app.state.clock()
        return operate(
            db,
            admin,
            "admin",
            key,
            f"cards.{card_id}.preview",
            body.model_dump(exclude_unset=True),
            now,
            lambda: make_preview(db, require_card(db, card_id), admin.id, body.revision, now),
        )

    @router.post("/cards/{card_id}/publish", response_model=CardView)
    def publish(
        card_id: str,
        body: PublishCard,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        now = request.app.state.clock()
        return operate(
            db,
            admin,
            "admin",
            key,
            f"cards.{card_id}.publish",
            body.model_dump(exclude_unset=True),
            now,
            lambda: publish_version(
                db, require_card(db, card_id), admin.id, body.revision, body.preview_id, now
            ),
        )

    @router.post("/cards/{card_id}/offline", response_model=CardView)
    def offline(
        card_id: str,
        body: Revision,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
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
            db,
            admin,
            "admin",
            key,
            f"cards.{card_id}.offline",
            body.model_dump(exclude_unset=True),
            now,
            execute,
        )

    @router.delete("/cards/{card_id}", response_model=DeletedCard)
    def delete(
        card_id: str,
        body: Revision,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
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
            db,
            admin,
            "admin",
            key,
            f"cards.{card_id}.delete",
            body.model_dump(exclude_unset=True),
            now,
            execute,
        )

    return router


def mini_routes():
    router = APIRouter(prefix="/api/mini/v1", tags=["published learning content"])

    @router.get("/cards", response_model=Page[CardBrief])
    def listing(
        request: Request,
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=50),
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        query = select(Card).where(Card.status == "published", Card.deleted_at.is_(None))
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        rows = db.scalars(
            query.order_by(Card.sort_order, Card.id).offset((page - 1) * limit).limit(limit)
        ).all()
        ids = [card.id for card in rows]
        versions = {
            v.id: v
            for v in db.scalars(
                select(CardVersion).where(
                    CardVersion.id.in_([card.current_version_id for card in rows])
                )
            )
        }
        images = {
            m.id: m
            for m in db.scalars(
                select(Media).where(
                    Media.id.in_([v.payload["image_id"] for v in versions.values()])
                )
            )
        }
        completed = set(
            db.scalars(
                select(Completion.card_id).where(
                    Completion.user_id == user.id, Completion.card_id.in_(ids)
                )
            )
        )
        daily = set(
            db.scalars(
                select(DailyLearning.card_id).where(
                    DailyLearning.user_id == user.id,
                    DailyLearning.card_id.in_(ids),
                    DailyLearning.date == business_date(request.app.state.clock()),
                )
            )
        )
        favorites = set(
            db.scalars(
                select(Favorite.card_id).where(
                    Favorite.user_id == user.id, Favorite.card_id.in_(ids)
                )
            )
        )
        items = []
        for card in rows:
            assert card.current_version_id is not None
            version = versions[card.current_version_id]
            image = images.get(version.payload["image_id"])
            items.append(
                {
                    "id": card.id,
                    "name": version.payload["name"],
                    "version_id": version.id,
                    "thumbnail_id": image.thumbnail_id if image else None,
                    "published_at": timestamp(version.published_at),
                    "state": {
                        "completed": card.id in completed,
                        "today_completed": card.id in daily,
                        "favorite": card.id in favorites,
                    },
                }
            )
        return {"items": items, "total": total, "page": page, "limit": limit}

    @router.get("/cards/{card_id}", response_model=PublishedDetail)
    def detail(
        card_id: str,
        request: Request,
        version_id: str | None = None,
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        card, version = published_card(db, card_id, version_id)
        audio = db.get(Media, version.payload["audio_id"])
        return {
            "audio_duration": audio.duration if audio else None,
            "card_id": card.id,
            "version_id": version.id,
            "content": version.payload,
            "published_at": timestamp(version.published_at),
            "state": card_state(db, user.id, card.id, request.app.state.clock()),
        }

    return router
