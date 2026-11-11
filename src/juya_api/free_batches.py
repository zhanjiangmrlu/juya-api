"""Frozen previews and independently committed, fenced free-access batch execution."""

import json
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .access_models import AccessHistory, FreePolicy
from .content_models import Card, CardDraft, CardVersion
from .content_service import catalog_lock as scene_lock
from .database import timestamp
from .dependencies import administrator, database, operation_key
from .errors import DomainError
from .free_access import free_view
from .free_batch_models import FreeAccessBatch, FreeAccessBatchItem
from .job_models import Job
from .jobs import enqueue, finish, lock_admin_job
from .listening_models import ListeningArticle, ListeningCategory, ListeningPolicy, ListeningVersion
from .listening_service import catalog_lock as listening_lock
from .models import Administrator, identifier
from .security import decrypt, encrypt
from .transactions import operate


class FreeBatchPreviewRequest(BaseModel):
    content_type: Literal["scene", "listening"]
    ids: list[str] = Field(
        min_length=1,
        title="明确选择的内容标识集合",
        description="按稳定ID去重，不受本页十条或调度每轮五十的限制",
    )
    is_free: bool


class FreeBatchItem(BaseModel):
    content_id: str
    name: str
    version_id: str | None = None
    free_revision: int | None = None
    is_free: bool | None = None
    status: Literal["pending", "succeeded", "skipped", "failed"]
    reason: str | None = None
    message: str | None = None


class FreeBatchPreview(BaseModel):
    content_type: Literal["scene", "listening"]
    is_free: bool
    total: int
    applicable: int
    skipped: int
    items: list[FreeBatchItem]
    preview_token: str


class FreeBatchSubmit(BaseModel):
    preview_token: str
    items: list[FreeBatchItem]


class FreeBatchResult(BaseModel):
    id: str
    job_id: str
    parent_id: str | None
    content_type: Literal["scene", "listening"]
    is_free: bool
    state: str
    total: int
    pending: int
    succeeded: int
    skipped: int
    failed: int
    created_at: str
    items: list[FreeBatchItem]


def model_for(kind):
    """Resolve a namespace controlled exclusively by the validated content kind."""
    return Card if kind == "scene" else ListeningArticle


def inspect_item(db, kind, content_id, target, *, lock=False):
    """Read current publication, deletion and category eligibility for one selected ID."""
    model = model_for(kind)
    query = select(model).where(model.id == content_id)
    if lock:
        query = query.with_for_update()
    row = db.scalar(query.execution_options(populate_existing=True))
    item = dict(
        content_id=content_id,
        name=content_id,
        version_id=None,
        free_revision=None,
        is_free=None,
        status="pending",
        reason=None,
        message=None,
    )
    reason, message = None, None
    if row is None:
        reason, message = "content_missing", "内容不存在"
    else:
        version_id = row.current_version_id if kind == "scene" else row.version_id
        if kind == "scene":
            version = db.get(CardVersion, version_id) if version_id else None
            draft = db.get(CardDraft, content_id)
            payload = version.payload if version else draft.payload if draft else {}
            item["name"] = payload.get("name", content_id)
        else:
            version = db.get(ListeningVersion, version_id) if version_id else None
            payload = version.payload if version else row.payload
            item["name"] = payload.get("title_zh", content_id)
        item.update(version_id=version_id, free_revision=row.free_revision, is_free=row.is_free)
        if row.deleted_at:
            reason, message = "content_deleted", "内容已删除"
        elif row.status != "published" or not version_id or not version:
            reason, message = "not_published", "内容当前未有效发布"
        elif kind == "listening" and (
            not (category := db.get(ListeningCategory, row.category_id)) or category.deleted_at
        ):
            reason, message = "permission_denied", "所属分类不可用，无操作权限"
        elif row.is_free == target:
            reason, message = "already_target", "已是目标免费状态，无需重复修改"
    if reason:
        item.update(status="skipped", reason=reason, message=message)
    return item, row


def result_view(db, batch):
    """Return every selected item including original skips and completed receipts."""
    rows = db.scalars(
        select(FreeAccessBatchItem)
        .where(FreeAccessBatchItem.batch_id == batch.id)
        .order_by(FreeAccessBatchItem.position)
    ).all()
    job = db.get(Job, batch.job_id)
    items = [
        {**x.snapshot, "status": x.status, "reason": x.reason, "message": x.message} for x in rows
    ]
    counts = {
        s: sum(x.status == s for x in rows) for s in ("pending", "succeeded", "skipped", "failed")
    }
    return dict(
        id=batch.id,
        job_id=batch.job_id,
        parent_id=batch.parent_id,
        content_type=batch.content_type,
        is_free=batch.is_free,
        state=job.state,
        total=len(rows),
        created_at=timestamp(batch.created_at),
        items=items,
        **counts,
    )


def require_batch(db, batch_id, admin_id):
    """Enforce the original administrator's ownership on reads and failed-subset retries."""
    batch = db.get(FreeAccessBatch, batch_id)
    if not batch or batch.admin_id != admin_id:
        raise DomainError(404, "free_batch_missing", "免费设置任务不存在或无权查看")
    return batch


def routes():
    """Register shared scenes/listening previews, task acceptance, lookup and explicit retries."""
    router = APIRouter(prefix="/api/admin/v1/free-access-batches", tags=["跨页免费设置"])

    @router.post(
        "/preview",
        response_model=FreeBatchPreview,
        summary="预览跨页免费集合",
        description="重读完整选择的发布及权限状态，不写业务；冻结适用和跳过名单供明确确认",
    )
    def preview(
        body: FreeBatchPreviewRequest,
        request: Request,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        """Preview all deduplicated IDs without creating a task or changing business data."""
        items = [
            inspect_item(db, body.content_type, i, body.is_free)[0] for i in dict.fromkeys(body.ids)
        ]
        frozen = dict(
            admin_id=admin.id, content_type=body.content_type, is_free=body.is_free, items=items
        )
        token = encrypt(request.app.state.settings, json.dumps(frozen, ensure_ascii=False))
        return dict(
            content_type=body.content_type,
            is_free=body.is_free,
            total=len(items),
            applicable=sum(i["status"] == "pending" for i in items),
            skipped=sum(i["status"] == "skipped" for i in items),
            items=items,
            preview_token=token,
        )

    def accept(body, request, admin, key, db, parent_id=None):
        """Validate an authenticated preview and accept precisely its displayed applicable set."""
        payload = body.model_dump()

        def execute():
            """Freeze skips as skips, keeping retries in a separate immutable child batch."""
            try:
                frozen = json.loads(decrypt(request.app.state.settings, body.preview_token) or "{}")
            except Exception:
                raise DomainError(409, "free_preview_invalid", "预览已失效，请重新核对") from None
            pending = [i for i in frozen.get("items", []) if i["status"] == "pending"]
            if (
                frozen.get("admin_id") != admin.id
                or not pending
                or pending != [i.model_dump() for i in body.items]
            ):
                raise DomainError(
                    409, "free_preview_changed", "提交集合与已展示适用集合不一致，请重新核对"
                )
            if parent_id:
                parent = require_batch(db, parent_id, admin.id)
                failed = set(
                    db.scalars(
                        select(FreeAccessBatchItem.content_id).where(
                            FreeAccessBatchItem.batch_id == parent_id,
                            FreeAccessBatchItem.status == "failed",
                        )
                    )
                )
                if (
                    parent.content_type != frozen["content_type"]
                    or parent.is_free != frozen["is_free"]
                    or not {i["content_id"] for i in frozen["items"]} <= failed
                ):
                    raise DomainError(
                        409, "free_retry_invalid", "仅可重新核对并重试原任务明确失败的项"
                    )
            batch_id = identifier()
            job = enqueue(
                db,
                "free_access.batch",
                "admin",
                admin.id,
                {"batch_id": batch_id},
                request.app.state.clock(),
                settings=request.app.state.settings,
            )
            batch = FreeAccessBatch(
                id=batch_id,
                admin_id=admin.id,
                job_id=job.id,
                parent_id=parent_id,
                content_type=frozen["content_type"],
                is_free=frozen["is_free"],
                created_at=request.app.state.clock(),
            )
            db.add(batch)
            db.flush()
            for position, item in enumerate(frozen["items"]):
                db.add(
                    FreeAccessBatchItem(
                        batch_id=batch_id,
                        content_id=item["content_id"],
                        position=position,
                        snapshot=item,
                        status=item["status"],
                        reason=item["reason"],
                        message=item["message"],
                    )
                )
            db.flush()
            return result_view(db, batch)

        return operate(
            db,
            admin,
            "admin",
            key,
            "free.batch:" + (parent_id or "new"),
            payload,
            request.app.state.clock(),
            execute,
        )

    @router.post(
        "",
        response_model=FreeBatchResult,
        summary="接受跨页免费任务",
        description="按原操作键接受已展示适用集合，逐项执行并保留完整回执",
    )
    def create(
        body: FreeBatchSubmit,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        """Accept one frozen cross-page operation with a recoverable durable operation key."""
        return accept(body, request, admin, key, db)

    @router.get(
        "/{batch_id}",
        response_model=FreeBatchResult,
        summary="查询免费任务完整结果",
        description="仅原管理员可查成功、跳过、失败及待处理名单；未知先查原任务",
    )
    def read(
        batch_id: str,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        """Read the original task before considering a retry after a lost response."""
        return result_view(db, require_batch(db, batch_id, admin.id))

    @router.post(
        "/{batch_id}/retry",
        response_model=FreeBatchResult,
        summary="重试原任务失败子集",
        description="仅接受重新预览确认的原失败项，保留父子批次及全部历史",
    )
    def retry(
        batch_id: str,
        body: FreeBatchSubmit,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        """Accept only freshly previewed failures without redoing successes or original skips."""
        return accept(body, request, admin, key, db, batch_id)

    return router


def run_batch(settings, sessions, job, now):
    """Commit each mutation, audit and receipt together under the winning worker lease."""
    batch_id = job["payload"]["batch_id"]
    with sessions() as db:
        ids = db.scalars(
            select(FreeAccessBatchItem.content_id)
            .where(FreeAccessBatchItem.batch_id == batch_id)
            .order_by(FreeAccessBatchItem.position)
        ).all()
    for content_id in ids:
        with sessions.begin() as db:
            lock_admin_job(db, job["id"])
            task = db.scalar(select(Job).where(Job.id == job["id"]).with_for_update())
            if (
                not task
                or task.state != "running"
                or task.lease != job["lease"]
                or task.lease_expires_at <= now()
            ):
                return
            batch = db.get(FreeAccessBatch, batch_id)
            (scene_lock if batch.content_type == "scene" else listening_lock)(db)
            item = db.get(FreeAccessBatchItem, (batch_id, content_id))
            if item.status != "pending":
                continue
            try:
                with db.begin_nested():
                    current, row = inspect_item(
                        db, batch.content_type, content_id, batch.is_free, lock=True
                    )
                    reason, message = None, None
                    if not db.get(Administrator, batch.admin_id):
                        reason, message = "permission_denied", "管理员资格已失效"
                    elif current["version_id"] != item.snapshot["version_id"]:
                        reason, message = "publication_changed", "发布版本已变化，请重新核对"
                    elif current["free_revision"] != item.snapshot["free_revision"]:
                        reason, message = "free_access_changed", "免费设置已变化，请重新核对"
                    elif current["status"] != "pending":
                        reason, message = current["reason"], current["message"]
                    if reason:
                        item.status, item.reason, item.message = "failed", reason, message
                    else:
                        before = dict(
                            content_type=batch.content_type,
                            content_id=content_id,
                            batch_id=batch_id,
                            **free_view(row),
                        )
                        row.is_free, row.free_revision = batch.is_free, row.free_revision + 1
                        policy = db.get(
                            FreePolicy if batch.content_type == "scene" else ListeningPolicy, 1
                        )
                        if policy:
                            policy.revision += 1
                        db.add(
                            AccessHistory(
                                admin_id=batch.admin_id,
                                action=batch.content_type + ".free.batch",
                                before=before,
                                after={**before, **free_view(row)},
                                occurred_at=now(),
                            )
                        )
                        item.status = "succeeded"
                    item.completed_at = now()
            except Exception as error:
                item.status = "failed"
                item.reason = error.code if isinstance(error, DomainError) else "item_failed"
                item.message = (
                    error.message
                    if isinstance(error, DomainError)
                    else "本项处理失败，请重新核对后重试"
                )
                item.completed_at = now()
    finish(sessions, job["id"], job["lease"], now(), {"batch_id": batch_id})
