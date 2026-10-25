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
from .access_models import AccessHistory, FreePolicy, LearningAuthorization
from .access_service import (
    authorization,
    free_ids,
    learning_access,
    policy,
    preview_token,
    proposed_authorization,
    read_preview,
)
from .content_models import Card, SettingCounter
from .content_service import catalog_lock
from .database import timestamp
from .dependencies import administrator, database, learner, operation_key
from .errors import DomainError
from .learning_service import business_date, card_state, card_summary
from .models import User
from .publication_api import catalog
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
        config, ordered = policy(db), catalog(db)
        old_ids, next_ids = (
            free_ids(db, config["free_count"]),
            [r["id"] for r in ordered["items"][: body.free_count]],
        )
        items = [
            {**r, "change": "retained" if r["id"] in old_ids else "added"}
            for r in ordered["items"][: body.free_count]
        ]
        values = {
            "free_count": body.free_count,
            "revision": config["revision"],
            "catalog_version": ordered["version"],
        }
        return {
            **config,
            "proposed_count": body.free_count,
            "total": len(items),
            "page": page,
            "limit": limit,
            "items": items[(page - 1) * limit : page * limit],
            "added_count": len(set(next_ids) - set(old_ids)),
            "removed_count": len(set(old_ids) - set(next_ids)),
            "removed": [r for r in ordered["items"] if r["id"] in set(old_ids) - set(next_ids)],
            "preview_token": preview_token(
                request.app.state.settings,
                admin.id,
                "free-policy",
                values,
                request.app.state.clock(),
            ),
        }

    @router.put(base, response_model=PolicyView)
    def save_policy(
        body: Confirmation,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        def execute():
            now = request.app.state.clock()
            data = read_preview(
                request.app.state.settings, body.preview_token, admin.id, "free-policy", now
            )
            catalog_lock(db)
            before = policy(db)
            if (
                before["revision"] != data["revision"]
                or catalog(db)["version"] != data["catalog_version"]
            ):
                raise DomainError(
                    409, "free_preview_changed", "发布场景或排序已变化，请重新核对免费名单"
                )
            if (
                not before["enabled"]
                and request.app.state.settings.environment != "local"
                and not request.app.state.settings.learning_access_activation_ready
            ):
                raise DomainError(
                    409, "access_rollout_not_ready", "服务版本尚未就绪，暂不能启用学习授权"
                )
            row = db.get(FreePolicy, 1)
            if row is None:
                row = FreePolicy(id=1, revision=0)
                db.add(row)
            if before["enabled"] and row.free_count == data["free_count"]:
                return {**before, "actual_free_count": len(free_ids(db, row.free_count))}
            contract = db.get(SettingCounter, "schema_contract")
            if contract:
                contract.value = 2
            row.enabled, row.free_count, row.revision = (
                True,
                data["free_count"],
                before["revision"] + 1,
            )
            db.flush()
            after = policy(db)
            db.add(
                AccessHistory(
                    admin_id=admin.id,
                    action="free-policy",
                    before=before,
                    after=after,
                    occurred_at=now,
                )
            )
            return {**after, "actual_free_count": len(free_ids(db, row.free_count))}

        return operate(
            db,
            admin,
            "admin",
            key,
            "learning.free-policy",
            body.model_dump(),
            request.app.state.clock(),
            execute,
        )

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
