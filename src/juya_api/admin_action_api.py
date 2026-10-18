"""Frozen management actions reuse durable per-card jobs and role-scoped receipts."""

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .admin_action_models import AdminActionBatch, AdminActionItem
from .content_models import Card, CardDraft
from .content_service import card_view, require_card, revision_matches
from .database import timestamp
from .dependencies import administrator, database, operation_key
from .errors import DomainError
from .job_models import Job
from .jobs import enqueue
from .transactions import operate

REVIEW_ERRORS = {
    "card_changed",
    "revision_changed",
    "card_deleted",
    "card_missing",
    "card_not_published",
}


class ActionSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    card_id: str = Field(min_length=1, max_length=36)
    revision: int = Field(ge=1)
    status: Literal["draft", "published", "offline", "deleted", "missing"]
    version_id: str | None = Field(default=None, max_length=36)


class CreateActionBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["offline", "delete"]
    confirmed: Literal[True]
    items: list[ActionSelection] = Field(min_length=1, max_length=10)
    skipped: list[ActionSelection] = Field(default_factory=list, max_length=10)


class ActionResult(BaseModel):
    id: str
    card_id: str
    name: str
    state: str
    error_code: str | None
    job_id: str | None
    needs_review: bool


class ActionBatchView(BaseModel):
    id: str
    action: Literal["offline", "delete"]
    created_at: str
    items: list[ActionResult]


def validate_snapshot(db, value):
    """Publishing without a new candidate still changes the confirmed live version."""
    card = require_card(db, value.card_id)
    revision_matches(db.get(CardDraft, card.id), value.revision)
    if card.status != value.status or card.current_version_id != value.version_id:
        raise DomainError(409, "card_changed", "卡片状态或发布版本已变化，请重新核对")
    return card


def owned(db, batch_id, admin_id):
    """Accepted actions remain readable only to their administrator."""
    batch = db.get(AdminActionBatch, batch_id)
    if not batch or batch.admin_id != admin_id:
        raise DomainError(404, "batch_missing", "未找到本次管理操作")
    return batch


def view(db, batch):
    """Derive results from current durable jobs rather than a stale acceptance snapshot."""
    items = db.scalars(
        select(AdminActionItem)
        .where(AdminActionItem.batch_id == batch.id)
        .order_by(AdminActionItem.position)
    ).all()
    result = []
    for item in items:
        job = db.get(Job, item.job_id) if item.job_id else None
        error = job.error_code if job else item.skip_reason
        result.append(
            {
                "id": item.id,
                "card_id": item.card_id,
                "name": item.name,
                "state": job.state if job else "skipped",
                "error_code": error,
                "job_id": item.job_id,
                "needs_review": error in REVIEW_ERRORS,
            }
        )
    return {
        "id": batch.id,
        "action": batch.action,
        "created_at": timestamp(batch.created_at),
        "items": result,
    }


def action_job(db, settings, admin_id, item, action, now):
    """Each task carries only the original applicable object's frozen preconditions."""
    item.job_id = enqueue(
        db,
        "card.action",
        "admin",
        admin_id,
        {
            "action": action,
            "card_id": item.card_id,
            "revision": item.revision,
            "status": item.status,
            "version_id": item.version_id,
        },
        now,
        settings=settings,
    ).id


def routes():
    router = APIRouter(prefix="/api/admin/v1", tags=["durable management actions"])

    @router.post("/card-action-batches", status_code=201, response_model=ActionBatchView)
    def create(
        body: CreateActionBatch,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        now = request.app.state.clock()

        def execute():
            selected = [*body.items, *body.skipped]
            if len(selected) > 10 or len({i.card_id for i in selected}) != len(selected):
                raise DomainError(422, "batch_selection", "请选择本页不重复的最多10张卡片")
            batch = AdminActionBatch(admin_id=admin.id, action=body.action, created_at=now)
            db.add(batch)
            db.flush()
            for position, value in enumerate(selected):
                card = db.get(Card, value.card_id)
                name = card_view(db, card)["display_name"] if card else "卡片已不可用"
                item = AdminActionItem(
                    batch_id=batch.id,
                    card_id=value.card_id,
                    name=name,
                    revision=value.revision,
                    status=value.status,
                    version_id=value.version_id,
                    position=position,
                )
                if position >= len(body.items):
                    item.skip_reason = "not_applicable"
                else:
                    action_job(db, request.app.state.settings, admin.id, item, body.action, now)
                db.add(item)
            db.flush()
            return view(db, batch)

        return operate(db, admin, "admin", key, "card.actions", body.model_dump(), now, execute)

    @router.get("/card-action-batches", response_model=list[ActionBatchView])
    def recent(admin=Depends(administrator), db: Session = Depends(database, scope="function")):
        batches = db.scalars(
            select(AdminActionBatch)
            .where(AdminActionBatch.admin_id == admin.id)
            .order_by(AdminActionBatch.created_at.desc(), AdminActionBatch.id.desc())
            .limit(10)
        ).all()
        return [view(db, batch) for batch in batches]

    @router.get("/card-action-batches/{batch_id}", response_model=ActionBatchView)
    def read(
        batch_id: str,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        return view(db, owned(db, batch_id, admin.id))

    @router.post("/card-action-batches/{batch_id}/retry", response_model=ActionBatchView)
    def retry(
        batch_id: str,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        now = request.app.state.clock()

        def execute():
            batch = owned(db, batch_id, admin.id)
            for item in db.scalars(
                select(AdminActionItem).where(AdminActionItem.batch_id == batch.id)
            ):
                job = db.get(Job, item.job_id) if item.job_id else None
                if not job or job.state != "failed":
                    continue
                try:
                    validate_snapshot(db, item)
                except DomainError as error:
                    job.error_code = error.code
                    continue
                action_job(db, request.app.state.settings, admin.id, item, batch.action, now)
            db.flush()
            return view(db, batch)

        return operate(db, admin, "admin", key, "card.actions.retry:" + batch_id, {}, now, execute)

    return router
