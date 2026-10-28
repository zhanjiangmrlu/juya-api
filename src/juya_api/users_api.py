"""Administrator-only, audited read access to real users and unified statistics."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from .access_models import LearningAuthorization
from .access_service import authorization
from .auth import user_view
from .content_models import Card
from .database import timestamp
from .dependencies import administrator, database, write_transaction
from .errors import DomainError
from .learning_models import Checkin
from .learning_service import (
    business_date,
    checkin_records,
    day_bounds,
    day_records,
    learning_records,
    statistics,
)
from .listening_models import ListeningArticle
from .models import Audit, User
from .response_contracts import (
    AdminUser,
    AdminUserPage,
    CheckinRecord,
    DailyRecords,
    LearningRecord,
    Overview,
    Page,
)
from .security import lookup
from .user_numbers import searched_user_number, user_code


def require_user(db, user_id):
    user = db.get(User, user_id)
    if not user:
        raise DomainError(404, "user_missing", "未找到此用户")
    return user


def routes():
    router = APIRouter(prefix="/api/admin/v1", tags=["read-only learners and statistics"])

    @router.get("/statistics", response_model=Overview)
    def overview(
        request: Request,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        now = request.app.state.clock()
        today = business_date(now)
        start, end = day_bounds(today)
        row = db.execute(
            select(
                select(func.count()).select_from(User).scalar_subquery(),
                select(func.count())
                .select_from(User)
                .where(User.registered_at >= start, User.registered_at < end)
                .scalar_subquery(),
                select(func.count())
                .select_from(Card)
                .where(Card.status == "published", Card.deleted_at.is_(None))
                .scalar_subquery(),
            )
        ).one()
        return {
            "published_article_count": db.scalar(
                select(func.count())
                .select_from(ListeningArticle)
                .where(
                    ListeningArticle.status == "published", ListeningArticle.deleted_at.is_(None)
                )
            )
            or 0,
            "user_count": row[0],
            "new_users_today": row[1],
            "published_card_count": row[2],
            "statistical_date": today.isoformat(),
            "updated_at": timestamp(now),
        }

    @router.get("/users", response_model=AdminUserPage, dependencies=[Depends(write_transaction)])
    def listing(
        request: Request,
        search: str = Query("", max_length=200),
        authorization_status: Literal["all", "none", "active", "expired"] = "all",
        registered: Literal["all", "today"] = "all",
        checkin: Literal["all", "checked", "unchecked"] = "all",
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        now, settings = request.app.state.clock(), request.app.state.settings
        today = business_date(now)
        query = select(User).outerjoin(
            LearningAuthorization, LearningAuthorization.user_id == User.id
        )
        active_grant = and_(
            LearningAuthorization.revoked_at.is_(None), LearningAuthorization.expires_on >= today
        )
        expired_grant = and_(
            LearningAuthorization.revoked_at.is_(None), LearningAuthorization.expires_on < today
        )
        if authorization_status == "active":
            query = query.where(active_grant)
        elif authorization_status == "expired":
            query = query.where(expired_grant)
        elif authorization_status == "none":
            query = query.where(
                or_(
                    LearningAuthorization.user_id.is_(None),
                    LearningAuthorization.revoked_at.is_not(None),
                )
            )
        if search.strip():
            value = search.strip()
            query = query.where(
                or_(
                    User.id.contains(value, autoescape=True),
                    User.user_number == searched_user_number(value),
                    User.nickname.contains(value, autoescape=True),
                    User.phone_digest == lookup(settings, "contact:phone", value),
                    User.wechat_digest == lookup(settings, "contact:wechat", value),
                )
            )
        if registered == "today":
            start, end = day_bounds(today)
            query = query.where(User.registered_at >= start, User.registered_at < end)
        checked = exists(
            select(Checkin.user_id).where(Checkin.user_id == User.id, Checkin.date == today)
        )
        if checkin == "checked":
            query = query.where(checked)
        elif checkin == "unchecked":
            query = query.where(~checked)
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        page = min(page, max(1, ((total or 0) + limit - 1) // limit))
        rows = db.scalars(
            query.order_by(User.registered_at.desc(), User.id)
            .offset((page - 1) * limit)
            .limit(limit)
        ).all()
        db.add(Audit(admin_id=admin.id, action="users.list", occurred_at=now))
        return {
            "items": [
                {
                    **user_view(user, settings),
                    "user_code": user_code(user.user_number),
                    "authorization": authorization(db, user.id, now),
                    "statistics": statistics(db, user.id, now),
                }
                for user in rows
            ],
            "total": total,
            "page": page,
            "limit": limit,
            "statistical_date": today.isoformat(),
        }

    @router.get(
        "/users/{user_id}", response_model=AdminUser, dependencies=[Depends(write_transaction)]
    )
    def detail(
        user_id: str,
        request: Request,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        user = require_user(db, user_id)
        now = request.app.state.clock()
        db.add(Audit(admin_id=admin.id, action="users.view", object_id=user.id, occurred_at=now))
        return {
            **user_view(user, request.app.state.settings),
            "user_code": user_code(user.user_number),
            "authorization": authorization(db, user.id, now),
            "statistics": statistics(db, user.id, now),
        }

    @router.get("/users/{user_id}/learning-records", response_model=Page[LearningRecord])
    def learned(
        user_id: str,
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        require_user(db, user_id)
        return learning_records(db, user_id, page, limit)

    @router.get("/users/{user_id}/checkins", response_model=Page[CheckinRecord])
    def checkins(
        user_id: str,
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        require_user(db, user_id)
        return checkin_records(db, user_id, page, limit)

    @router.get("/users/{user_id}/checkins/{day}", response_model=DailyRecords)
    def day_detail(
        user_id: str,
        day: date,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        require_user(db, user_id)
        return day_records(db, user_id, day)

    return router
