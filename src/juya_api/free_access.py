"""Per-object explicit free flags, independent revisions and transactional audit history."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import listening_contracts as C
from .access_models import AccessHistory, FreePolicy
from .content_models import Card
from .content_service import catalog_lock as scene_lock
from .dependencies import administrator, database, operation_key
from .errors import DomainError
from .listening_models import ListeningArticle, ListeningPolicy
from .listening_service import catalog_lock as listening_lock
from .transactions import operate


def free_view(row):
    """Expose configured state separately from effective publication availability."""
    version = row.current_version_id if isinstance(row, Card) else row.version_id
    return {
        "is_free": row.is_free,
        "revision": row.free_revision,
        "effective": bool(
            row.is_free and row.status == "published" and version and not row.deleted_at
        ),
    }


def require_object(db, model, identifier, *, lock=False):
    """Resolve a stable object; deleted objects cannot be revived through free settings."""
    query = select(model).where(model.id == identifier)
    if lock:
        query = query.with_for_update()
    row = db.scalar(query.execution_options(populate_existing=True))
    if not row:
        raise DomainError(404, "free_content_missing", "内容不存在")
    if row.deleted_at:
        raise DomainError(410, "free_content_deleted", "内容已删除，不能更改免费设置")
    return row


def routes():
    """Register the same precise GET/PUT contract for scenes and listening articles."""
    router = APIRouter(prefix="/api/admin/v1", tags=["explicit free access"])

    def register(path, model, kind):
        """Bind model and lock namespace once rather than infer from request data."""

        @router.get(path + "/{identifier}/free-access", response_model=C.FreeAccess)
        def read(
            identifier: str,
            admin=Depends(administrator),
            db: Session = Depends(database, scope="function"),
        ):
            """Read authoritative free state after a pending or unknown response."""
            return free_view(require_object(db, model, identifier))

        @router.put(path + "/{identifier}/free-access", response_model=C.FreeAccess)
        def save(
            identifier: str,
            body: C.FreeAccessUpdate,
            request: Request,
            admin=Depends(administrator),
            key=Depends(operation_key),
            db: Session = Depends(database, scope="function"),
        ):
            """Change exactly one flag and persist its receipt and audit in the same transaction."""

            def execute():
                """Fence catalog, object and free revision in the established order."""
                (scene_lock if model is Card else listening_lock)(db)
                row = require_object(db, model, identifier, lock=True)
                if row.free_revision != body.revision:
                    raise DomainError(
                        409, "free_access_changed", "免费设置已变化，请刷新后重新确认"
                    )
                before = {"content_type": kind, "content_id": identifier, **free_view(row)}
                if row.is_free != body.is_free:
                    row.is_free, row.free_revision = body.is_free, row.free_revision + 1
                    policy = db.get(FreePolicy, 1) if model is Card else db.get(ListeningPolicy, 1)
                    if policy:
                        policy.revision += 1
                    db.flush()
                    db.add(
                        AccessHistory(
                            admin_id=admin.id,
                            action=kind + ".free",
                            before=before,
                            after={
                                "content_type": kind,
                                "content_id": identifier,
                                **free_view(row),
                            },
                            occurred_at=request.app.state.clock(),
                        )
                    )
                return free_view(row)

            return operate(
                db,
                admin,
                "admin",
                key,
                kind + ".free:" + identifier,
                body.model_dump(),
                request.app.state.clock(),
                execute,
            )

    register("/cards", Card, "scene")
    register("/listening/articles", ListeningArticle, "listening")
    return router
