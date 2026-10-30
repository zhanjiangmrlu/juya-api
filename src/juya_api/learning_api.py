"""Authenticated learner actions and read-only personal learning records."""

from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .access_service import require_access
from .content_models import Card
from .content_service import published_card
from .database import timestamp
from .dependencies import database, learner, operation_key
from .errors import DomainError
from .learning_models import Favorite
from .learning_service import (
    card_state,
    card_summary,
    checkin_records,
    complete_learning,
    day_records,
    learning_records,
    statistics,
)
from .response_contracts import (
    CardState,
    CheckinRecord,
    CompletionResponse,
    DailyRecords,
    FavoriteResponse,
    LearningRecord,
    Page,
    PersonalSummary,
    Statistics,
)
from .transactions import operate


class CurrentVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version_id: str = Field(min_length=1, max_length=36)


def routes():
    router = APIRouter(prefix="/api/mini/v1", tags=["personal learning"])

    @router.get("/me/statistics", response_model=Statistics)
    def stats(
        request: Request, user=Depends(learner), db: Session = Depends(database, scope="function")
    ):
        return statistics(db, user.id, request.app.state.clock())

    @router.post("/cards/{card_id}/complete", response_model=CompletionResponse)
    def complete(
        card_id: str,
        body: CurrentVersion,
        request: Request,
        user=Depends(learner),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        now = request.app.state.clock()
        return operate(
            db,
            user,
            "mini",
            key,
            f"cards.{card_id}.complete",
            body.model_dump(),
            now,
            lambda: complete_learning(db, user, card_id, body.version_id, now),
        )

    @router.put("/cards/{card_id}/favorite", response_model=FavoriteResponse)
    def favorite(
        card_id: str,
        body: CurrentVersion,
        request: Request,
        user=Depends(learner),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        now = request.app.state.clock()

        def execute():
            require_access(db, user.id, card_id, request.app.state.clock(), lock=True)
            db.scalar(
                select(Card)
                .where(Card.id == card_id)
                .with_for_update(read=True)
                .execution_options(populate_existing=True)
            )
            published_card(db, card_id, body.version_id)
            if db.get(Favorite, (user.id, card_id)) is None:
                db.add(Favorite(user_id=user.id, card_id=card_id, created_at=now))
                db.flush()
            return {"card_id": card_id, "favorite": True}

        return operate(
            db, user, "mini", key, f"cards.{card_id}.favorite", body.model_dump(), now, execute
        )

    @router.delete("/favorites/{card_id}", response_model=FavoriteResponse)
    def unfavorite(
        card_id: str,
        request: Request,
        user=Depends(learner),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        now = request.app.state.clock()

        def execute():
            favorite = db.get(Favorite, (user.id, card_id))
            if favorite:
                db.delete(favorite)
            return {"card_id": card_id, "favorite": False}

        return operate(db, user, "mini", key, f"cards.{card_id}.unfavorite", {}, now, execute)

    @router.get("/favorites", response_model=Page[PersonalSummary])
    def favorites(
        request: Request,
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=50),
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        query = (
            select(Favorite)
            .join(Card, Favorite.card_id == Card.id)
            .where(Favorite.user_id == user.id, Card.deleted_at.is_(None))
        )
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        page = min(page, max(1, ((total or 0) + limit - 1) // limit))
        rows = db.scalars(
            query.order_by(Favorite.created_at.desc(), Favorite.card_id)
            .offset((page - 1) * limit)
            .limit(limit)
        ).all()
        return {
            "items": [
                {
                    **card_summary(db, row.card_id, user.id),
                    "favorited_at": timestamp(row.created_at),
                    "state": card_state(db, user.id, row.card_id, request.app.state.clock()),
                }
                for row in rows
            ],
            "total": total,
            "page": page,
            "limit": limit,
        }

    @router.get("/cards/{card_id}/state", response_model=CardState)
    def state(
        card_id: str,
        request: Request,
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        published_card(db, card_id)
        return card_state(db, user.id, card_id, request.app.state.clock())

    @router.get("/cards/{card_id}/summary", response_model=PersonalSummary)
    def summary(
        card_id: str,
        request: Request,
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        from .learning_models import Completion

        if not db.get(Favorite, (user.id, card_id)) and not db.get(Completion, (user.id, card_id)):
            raise DomainError(404, "card_missing", "未找到本人记录中的场景卡")
        return {
            **card_summary(db, card_id, user.id),
            "state": card_state(db, user.id, card_id, request.app.state.clock()),
        }

    @router.get("/me/learning-records", response_model=Page[LearningRecord])
    def records(
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=50),
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        return learning_records(db, user.id, page, limit)

    @router.get("/me/checkins", response_model=Page[CheckinRecord])
    def checkins(
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=50),
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        return checkin_records(db, user.id, page, limit)

    @router.get("/me/checkins/{day}", response_model=DailyRecords)
    def day_detail(
        day: date, user=Depends(learner), db: Session = Depends(database, scope="function")
    ):
        return day_records(db, user.id, day)

    return router
