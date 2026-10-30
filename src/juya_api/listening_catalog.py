"""Reference-safe catalog deletion; historical rows are never cascaded or reassigned."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import listening_contracts as C
from . import listening_service as service
from .dependencies import administrator, database, operation_key
from .errors import DomainError
from .listening_models import (
    ListeningArticle,
    ListeningCandidate,
    ListeningCategory,
    ListeningTopic,
)
from .transactions import operate


def reference_counts(db, model, identifier):
    """Count every actual foreign-key reference, including deleted content and old imports."""
    if model is ListeningCategory:
        return {
            "topics": db.scalar(
                select(func.count())
                .select_from(ListeningTopic)
                .where(ListeningTopic.category_id == identifier)
            )
            or 0
        }
    articles = (ListeningArticle.topic_id == identifier) | (
        ListeningArticle.draft_topic_id == identifier
    )
    return {
        "articles": db.scalar(
            select(func.count())
            .select_from(ListeningArticle)
            .where(articles, ListeningArticle.deleted_at.is_(None))
        )
        or 0,
        "deleted_articles": db.scalar(
            select(func.count())
            .select_from(ListeningArticle)
            .where(articles, ListeningArticle.deleted_at.is_not(None))
        )
        or 0,
        "candidates": db.scalar(
            select(func.count())
            .select_from(ListeningCandidate)
            .where(ListeningCandidate.topic_id == identifier)
        )
        or 0,
    }


def delete_catalog(db, model, identifier, revision):
    """Delete one empty object under the common catalog lock and a version check."""
    row = db.scalar(
        select(model)
        .where(model.id == identifier)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise DomainError(404, "listening_catalog_missing", "分类或主题已不存在，请刷新")
    if row.revision != revision:
        raise DomainError(409, "listening_catalog_changed", "分类或主题已变化，请刷新后重新确认")
    references = reference_counts(db, model, identifier)
    if any(references.values()):
        historical = references.get("deleted_articles", 0) or references.get("candidates", 0)
        message = (
            "仍有历史文章或导入引用，不能删除；历史关联将保留"
            if historical
            else "仍有下属引用，请先迁移到其他分类或主题"
        )
        raise DomainError(409, "listening_catalog_referenced", message, {"references": references})
    db.delete(row)
    db.flush()
    service.changed(db)
    return {"id": identifier, "status": "success", "references": references}


def routes():
    router = APIRouter(prefix="/api/admin/v1/listening", tags=["listening administration"])

    def register(resource, model):
        @router.post(f"/{resource}/batch-delete", response_model=C.CatalogBatchDeleteResult)
        def batch_delete(
            body: C.BatchDelete,
            request: Request,
            admin=Depends(administrator),
            key=Depends(operation_key),
            db: Session = Depends(database, scope="function"),
        ):
            def execute():
                service.catalog_lock(db)
                results = []
                for item in body.items:
                    try:
                        with db.begin_nested():
                            result = delete_catalog(db, model, item.id, item.revision)
                        results.append(result)
                    except DomainError as error:
                        results.append(
                            {
                                "id": item.id,
                                "status": "failed",
                                "error": error.code,
                                "message": error.message,
                                "references": (error.details or {}).get("references", {}),
                            }
                        )
                service.audit(db, admin.id, resource + ".batch_delete", request.app.state.clock())
                return {"items": results}

            return operate(
                db,
                admin,
                "admin",
                key,
                "listening." + resource + ".batch_delete",
                body.model_dump(),
                request.app.state.clock(),
                execute,
            )

        @router.post(f"/{resource}/{{identifier}}/delete", response_model=C.CatalogDeleteResult)
        def single_delete(
            identifier: str,
            body: C.Revision,
            request: Request,
            admin=Depends(administrator),
            key=Depends(operation_key),
            db: Session = Depends(database, scope="function"),
        ):
            def execute():
                service.catalog_lock(db)
                result = delete_catalog(db, model, identifier, body.revision)
                service.audit(db, admin.id, resource + ".delete", request.app.state.clock())
                return result

            return operate(
                db,
                admin,
                "admin",
                key,
                "listening." + resource + ".delete:" + identifier,
                body.model_dump(),
                request.app.state.clock(),
                execute,
            )

    register("categories", ListeningCategory)
    register("topics", ListeningTopic)
    return router
