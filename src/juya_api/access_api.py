"""Role-separated learning access and preview-confirmed administrative operations."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .access_contracts import (
    AccessHistoryPage,
    AuthorizationView,
    CurrentAccess,
    FreePolicyPreview,
    GrantPreview,
    PolicyView,
)
from .access_models import AccessHistory, LearningAuthorization
from .access_service import (
    authorization,
    free_ids,
    learning_access,
    policy,
    preview_token,
    proposed_authorization,
    read_preview,
)
from .content_models import Card
from .database import timestamp
from .dependencies import administrator, database, learner, operation_key
from .errors import DomainError
from .learning_service import business_date, card_state, card_summary
from .models import User
from .response_contracts import LearningPermission, PersonalSummary
from .transactions import operate
from .users_api import require_user


class FreePreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    free_count: int = Field(strict=True, ge=0, le=2147483647)


class Confirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preview_token: str = Field(min_length=1, max_length=20000)


class AuthorizationPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["grant", "renew", "set_expiry", "revoke"]
    expires_on: date | None = None


class CardAccessView(BaseModel):
    summary: PersonalSummary
    access: LearningPermission


def history(db, user_id, page, limit):
    """Return chronological audited before/after values without private contact data."""
    query = select(AccessHistory).where(AccessHistory.user_id == user_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(AccessHistory.occurred_at.desc(), AccessHistory.id)
        .offset((page - 1) * limit)
        .limit(limit)
    )
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": [
            {
                "id": r.id,
                "action": r.action,
                "admin_id": r.admin_id,
                "before": r.before,
                "after": r.after,
                "occurred_at": timestamp(r.occurred_at),
            }
            for r in rows
        ],
    }


def admin_routes():
    """Only authenticated administrators can preview and commit access changes."""
    router = APIRouter(prefix="/api/admin/v1", tags=["learning authorization"])
    base = "/learning-access/free-policy"

    @router.get(base, response_model=PolicyView)
    def read_policy(
        admin=Depends(administrator), db: Session = Depends(database, scope="function")
    ):
        return {**policy(db), "actual_free_count": len(free_ids(db, policy(db)["free_count"]))}

    @router.get(base + "/history", response_model=AccessHistoryPage)
    def policy_history(
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        return history(db, None, page, limit)

    @router.post(base + "/preview", response_model=FreePolicyPreview)
    def preview_policy(
        body: FreePreview,
        request: Request,
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        """Reject obsolete configuration writes while retaining role authentication."""
        raise DomainError(410, "configuration_retired", "请使用分类管理和逐项免费设置")

    @router.put(base, response_model=PolicyView)
    def save_policy(
        body: Confirmation,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        """Reject obsolete configuration writes while retaining role authentication."""
        raise DomainError(410, "configuration_retired", "请使用分类管理和逐项免费设置")

    grant_path = "/users/{user_id}/learning-authorization"

    @router.get(grant_path, response_model=AuthorizationView)
    def read_grant(
        user_id: str,
        request: Request,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        require_user(db, user_id)
        return authorization(db, user_id, request.app.state.clock())

    @router.get(grant_path + "/history", response_model=AccessHistoryPage)
    def grant_history(
        user_id: str,
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        require_user(db, user_id)
        return history(db, user_id, page, limit)

    @router.post(grant_path + "/preview", response_model=GrantPreview)
    def preview_grant(
        user_id: str,
        body: AuthorizationPreview,
        request: Request,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        require_user(db, user_id)
        now = request.app.state.clock()
        before = authorization(db, user_id, now)
        after = proposed_authorization(db, user_id, body.action, body.expires_on, now)
        values = {
            "user_id": user_id,
            "revision": before["revision"],
            "day": business_date(now).isoformat(),
            **body.model_dump(mode="json"),
            "after": after,
        }
        return {
            "user_id": user_id,
            "before": before,
            "after": after,
            "preview_token": preview_token(
                request.app.state.settings, admin.id, "authorization", values, now
            ),
        }

    @router.put(grant_path, response_model=AuthorizationView)
    def save_grant(
        user_id: str,
        body: Confirmation,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        def execute():
            require_user(db, user_id)
            db.scalar(
                select(User)
                .where(User.id == user_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            now = request.app.state.clock()
            data = read_preview(
                request.app.state.settings, body.preview_token, admin.id, "authorization", now
            )
            before = authorization(db, user_id, now)
            if (
                data["user_id"] != user_id
                or data["revision"] != before["revision"]
                or data["day"] != business_date(now).isoformat()
            ):
                raise DomainError(409, "authorization_changed", "用户授权或日期已变化，请重新核对")
            after = proposed_authorization(
                db,
                user_id,
                data["action"],
                date.fromisoformat(data["expires_on"]) if data.get("expires_on") else None,
                now,
            )
            row = db.get(LearningAuthorization, user_id)
            if row is None:
                row = LearningAuthorization(user_id=user_id, revision=0)
                db.add(row)
            row.starts_on = date.fromisoformat(after["starts_on"])
            row.expires_on = (
                date.fromisoformat(after["expires_on"]) if after["expires_on"] else None
            )
            row.revoked_at = now if data["action"] == "revoke" else None
            row.revision = before["revision"] + 1
            db.flush()
            result = authorization(db, user_id, now)
            db.add(
                AccessHistory(
                    user_id=user_id,
                    admin_id=admin.id,
                    action=data["action"],
                    before=before,
                    after=result,
                    occurred_at=now,
                )
            )
            return result

        return operate(
            db,
            admin,
            "admin",
            key,
            "learning.authorization:" + user_id,
            body.model_dump(),
            request.app.state.clock(),
            execute,
        )

    return router


def mini_routes():
    """Expose only the caller's grant and safe scene access metadata."""
    router = APIRouter(prefix="/api/mini/v1", tags=["learning access"])

    @router.get("/learning-access", response_model=CurrentAccess)
    def current(
        request: Request, user=Depends(learner), db: Session = Depends(database, scope="function")
    ):
        return {
            **policy(db),
            "authorization": authorization(db, user.id, request.app.state.clock()),
            "server_now": timestamp(request.app.state.clock()),
        }

    @router.get("/cards/{card_id}/access", response_model=CardAccessView)
    def card_access(
        card_id: str,
        request: Request,
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        card = db.get(Card, card_id)
        if not card:
            raise DomainError(404, "card_missing", "场景卡暂不可用")
        if card.deleted_at or card.status != "published":
            from .learning_models import Completion, Favorite

            if not db.get(Completion, (user.id, card_id)) and not db.get(
                Favorite, (user.id, card_id)
            ):
                raise DomainError(410, "card_unavailable", "场景卡暂不可用")
        return {
            "summary": {
                **card_summary(db, card_id),
                "state": card_state(db, user.id, card_id, request.app.state.clock()),
            },
            "access": learning_access(db, user.id, card_id, request.app.state.clock()),
        }

    return router
