"""Thin role-specific scene HTTP adapters over the same publication domain."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from .access_service import (
    access_context,
    free_ids,
    free_uncompleted,
    learning_access,
    policy,
    require_access,
)
from .content_contracts import CreateCard, PublishCard, Revision, SaveCard
from .content_models import Card, CardDraft, CardVersion, Media
from .content_service import (
    card_view,
    create_candidate,
    lifecycle_action,
    make_preview,
    publish_version,
    published_card,
    require_card,
    save_candidate,
)
from .database import timestamp
from .dependencies import administrator, database, learner, operation_key, write_transaction
from .discovery_models import ReadingStart
from .import_models import ImportItem
from .import_service import owned_batch
from .learning_models import Completion, DailyLearning, Favorite
from .learning_service import business_date, card_state
from .persistence import insert_once
from .response_contracts import (
    AdminCardPage,
    CardPreview,
    CardView,
    DeletedCard,
    LearningCardPage,
    PublishedDetail,
    PublishedPreview,
)
from .transactions import operate


def admin_routes():
    router = APIRouter(prefix="/api/admin/v1", tags=["scene management"])

    @router.get("/cards", response_model=AdminCardPage)
    def listing(
        request: Request,
        status: str = "all",
        search: str = "",
        batch_id: str | None = Query(None, min_length=1, max_length=36),
        anchor_id: str | None = Query(None, min_length=1, max_length=36),
        page: int = Query(1, ge=1),
        limit: int = Query(10, ge=1),
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        """按最新发布倒序分页；未发布卡片使用创建时间，定位沿用相同排序"""
        limit = min(limit, 10)
        listed_at = func.coalesce(CardVersion.published_at, Card.created_at)
        query = (
            select(Card)
            .join(CardDraft)
            .outerjoin(CardVersion, CardVersion.id == Card.current_version_id)
            .where(Card.deleted_at.is_(None))
        )
        if batch_id:
            owned_batch(db, batch_id, admin.id)
            query = query.where(
                Card.id.in_(
                    select(ImportItem.saved_card_id).where(
                        ImportItem.batch_id == batch_id, ImportItem.saved_card_id.is_not(None)
                    )
                )
            )
        if status in {"draft", "published", "offline"}:
            query = query.where(Card.status == status)
        if search.strip():
            query = query.where(
                or_(
                    CardDraft.payload["name"].as_string().contains(search.strip(), autoescape=True),
                    func.lower(CardDraft.payload["title_en"].as_string()).contains(
                        search.strip().lower(), autoescape=True
                    ),
                    CardVersion.payload["name"]
                    .as_string()
                    .contains(search.strip(), autoescape=True),
                    func.lower(CardVersion.payload["title_en"].as_string()).contains(
                        search.strip().lower(), autoescape=True
                    ),
                )
            )
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        total_pages = ((total or 0) + limit - 1) // limit
        if anchor_id:
            anchor = db.execute(query.add_columns(listed_at).where(Card.id == anchor_id)).first()
            if anchor:
                anchor_card, anchor_time = anchor[0], anchor[1]
                preceding = query.where(
                    or_(
                        listed_at > anchor_time,
                        and_(listed_at == anchor_time, Card.id > anchor_card.id),
                    )
                )
                rank = db.scalar(select(func.count()).select_from(preceding.subquery())) or 0
                page = rank // limit + 1
        page = min(page, max(1, total_pages))
        rows = db.scalars(
            query.order_by(listed_at.desc(), Card.id.desc()).offset((page - 1) * limit).limit(limit)
        ).all()
        return {
            "learning_policy": {
                **policy(db),
                "actual_free_count": len(free_ids(db, policy(db)["free_count"])),
            },
            "items": [
                {
                    **card_view(db, card),
                    "is_free": card.id in free_ids(db, policy(db)["free_count"]),
                }
                for card in rows
            ],
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
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
            card = create_candidate(db, body.content, admin.id, now)
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
            card = save_candidate(db, card_id, body.revision, body.content, admin.id, now)
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
            return lifecycle_action(db, card_id, body.revision, "offline", admin.id, now)

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
            return lifecycle_action(db, card_id, body.revision, "delete", admin.id, now)

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

    @router.get("/cards", response_model=LearningCardPage)
    def listing(
        request: Request,
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=50),
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        """先按本人完成记录过滤再分页，并独立返回当前发布总数"""
        query = select(Card).where(Card.status == "published", Card.deleted_at.is_(None))
        published_total = db.scalar(select(func.count()).select_from(query.subquery()))
        query = query.where(
            Card.id.not_in(select(Completion.card_id).where(Completion.user_id == user.id))
        )
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
        started = set(
            db.scalars(
                select(ReadingStart.card_id).where(
                    ReadingStart.user_id == user.id, ReadingStart.card_id.in_(ids)
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
                    "access": learning_access(db, user.id, card.id, request.app.state.clock()),
                    "name": version.payload["name"],
                    "title_en": version.payload.get("title_en", ""),
                    "version_id": version.id,
                    "thumbnail_id": image.thumbnail_id if image else None,
                    "published_at": timestamp(version.published_at),
                    "vocabulary_count": len(version.payload.get("vocabulary") or []),
                    "chunk_count": len(version.payload.get("chunks") or []),
                    "state": {
                        "completed": card.id in completed,
                        "today_completed": card.id in daily,
                        "favorite": card.id in favorites,
                        "started": card.id in started,
                    },
                }
            )
        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "published_total": published_total,
            "learning_access": access_context(db, user.id, request.app.state.clock()),
            "free_uncompleted_total": free_uncompleted(db, user.id),
        }

    @router.get(
        "/cards/{card_id}",
        response_model=PublishedDetail,
        dependencies=[Depends(write_transaction)],
    )
    def detail(
        card_id: str,
        request: Request,
        version_id: str | None = None,
        mark_started: bool = True,
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        """读取卡片当前版本并仅为当前用户记录首次有效打开，不计成绩"""
        access = require_access(db, user.id, card_id, request.app.state.clock())
        card, version = published_card(db, card_id, version_id)
        # 列表缩略图缺失时仅补读素材元信息，不能当作用户已打开场景
        if mark_started:
            insert_once(
                db,
                ReadingStart,
                {"user_id": user.id, "card_id": card.id, "started_at": request.app.state.clock()},
                ["user_id", "card_id"],
            )
        audio = db.get(Media, version.payload["audio_id"])
        image = db.get(Media, version.payload["image_id"])
        reading = db.get(ReadingStart, (user.id, card.id))
        return {
            "access": access,
            "audio_duration": audio.duration if audio else None,
            "thumbnail_id": image.thumbnail_id if image else None,
            "card_id": card.id,
            "version_id": version.id,
            "content": version.payload,
            "published_at": timestamp(version.published_at),
            "state": card_state(db, user.id, card.id, request.app.state.clock()),
            "reading_position": reading.position
            if reading and reading.position and reading.position.get("version_id") == version.id
            else None,
            "reading_position_reset": bool(
                reading and reading.position and reading.position.get("version_id") != version.id
            ),
        }

    return router
