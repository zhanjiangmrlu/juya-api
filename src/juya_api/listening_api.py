"""Role-separated administration and learning of versioned thematic articles."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import listening_contracts as C
from . import listening_media as media
from . import listening_service as service
from .access_service import authorization, read_preview
from .content_models import Media
from .database import timestamp
from .dependencies import administrator, database, learner, operation_key
from .dictionary import DictionaryResult, TokenTarget, lookup
from .errors import DomainError
from .learning_models import Checkin
from .learning_service import day_records, statistics
from .listening_models import (
    ListeningArticle as Article,
)
from .listening_models import (
    ListeningCandidate,
    ListeningJob,
    ListeningTimeline,
)
from .listening_models import (
    ListeningCategory as Category,
)
from .listening_models import (
    ListeningCompletion as Completion,
)
from .listening_models import (
    ListeningDaily as Daily,
)
from .listening_models import (
    ListeningFavorite as Favorite,
)
from .listening_models import (
    ListeningTopic as Topic,
)
from .listening_timeline import body_tokens, timeline_view, validate_words
from .media_api import deliver
from .models import User
from .pronunciation import configuration, status
from .pronunciation import request as request_speech
from .pronunciation_api import SpeechState
from .pronunciation_models import Pronunciation
from .response_contracts import MediaMetadata, Page, Statistics
from .security import fingerprint
from .transactions import operate


def row_view(row):
    return {
        "id": row.id,
        "name": row.name,
        "sort_order": row.sort_order,
        "revision": row.revision,
        **(
            {
                "category_id": row.category_id,
                "description": row.description,
                "name_en": row.name_en or "",
            }
            if isinstance(row, Topic)
            else {"name_en": row.name_en}
        ),
    }


def page_view(db, query, page, limit, render):
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    page = min(page, max(1, (total + limit - 1) // limit))
    rows = db.scalars(query.offset((page - 1) * limit).limit(limit)).all()
    return {"items": [render(row) for row in rows], "total": total, "page": page, "limit": limit}


def admin_routes():
    router = APIRouter(prefix="/api/admin/v1/listening", tags=["listening administration"])

    @router.get("/categories", response_model=dict[str, list[C.Category]])
    def categories(admin=Depends(administrator), db: Session = Depends(database, scope="function")):
        return {
            "items": [
                row_view(r)
                for r in db.scalars(select(Category).order_by(Category.sort_order, Category.id))
            ]
        }

    @router.post("/categories", response_model=C.Category)
    def add_category(
        body: C.CategoryInput,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        def execute():
            service.catalog_lock(db)
            row = Category(**{**body.model_dump(), "name_en": body.name_en or ""})
            db.add(row)
            db.flush()
            service.changed(db)
            return row_view(row)

        return operate(
            db,
            admin,
            "admin",
            key,
            "listening.category.create",
            body.model_dump(),
            request.app.state.clock(),
            execute,
        )

    @router.put("/categories/{category_id}", response_model=C.Category)
    def edit_category(
        category_id: str,
        body: C.CategoryUpdate,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        def execute():
            service.catalog_lock(db)
            row = db.get(Category, category_id)
            if not row or row.revision != body.revision:
                raise DomainError(409, "listening_category_changed", "分类已变化，请刷新")
            row.name, row.sort_order, row.revision = body.name, body.sort_order, row.revision + 1
            if body.name_en is not None:
                row.name_en = body.name_en
            service.changed(db)
            return row_view(row)

        return operate(
            db,
            admin,
            "admin",
            key,
            "listening.category.update:" + category_id,
            body.model_dump(),
            request.app.state.clock(),
            execute,
        )

    @router.get("/topics", response_model=dict[str, list[C.Topic]])
    def topics(
        category_id: str | None = None,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        query = select(Topic).order_by(Topic.sort_order, Topic.id)
        if category_id:
            query = query.where(Topic.category_id == category_id)
        return {"items": [row_view(r) for r in db.scalars(query)]}

    @router.post("/topics", response_model=C.Topic)
    def add_topic(
        body: C.TopicInput,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        def execute():
            service.catalog_lock(db)
            if not db.get(Category, body.category_id):
                raise DomainError(422, "listening_category_missing", "请选择有效分类")
            row = Topic(
                **{
                    **body.model_dump(),
                    "description": body.description or "",
                    "name_en": body.name_en or "",
                }
            )
            db.add(row)
            db.flush()
            service.changed(db)
            return row_view(row)

        return operate(
            db,
            admin,
            "admin",
            key,
            "listening.topic.create",
            body.model_dump(),
            request.app.state.clock(),
            execute,
        )

    @router.put("/topics/{topic_id}", response_model=C.Topic)
    def edit_topic(
        topic_id: str,
        body: C.TopicUpdate,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        def execute():
            service.catalog_lock(db)
            row = db.get(Topic, topic_id)
            if not row or row.revision != body.revision:
                raise DomainError(409, "listening_topic_changed", "主题已变化，请刷新")
            if not db.get(Category, body.category_id):
                raise DomainError(422, "listening_category_missing", "请选择有效分类")
            row.name, row.category_id, row.sort_order = body.name, body.category_id, body.sort_order
            if body.description is not None:
                row.description = body.description
            if body.name_en is not None:
                row.name_en = body.name_en
            row.revision += 1
            service.changed(db)
            return row_view(row)

        return operate(
            db,
            admin,
            "admin",
            key,
            "listening.topic.update:" + topic_id,
            body.model_dump(),
            request.app.state.clock(),
            execute,
        )

    @router.get("/articles", response_model=Page[C.Article])
    def articles(
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=50),
        topic_id: str | None = None,
        category_id: str | None = None,
        status: str | None = None,
        batch_id: str | None = None,
        q: str = Query("", max_length=200),
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        query = select(Article).where(Article.deleted_at.is_(None))
        if category_id:
            query = query.join(
                Topic, func.coalesce(Article.draft_topic_id, Article.topic_id) == Topic.id
            ).where(Topic.category_id == category_id)
        for field, value in [
            (func.coalesce(Article.draft_topic_id, Article.topic_id), topic_id),
            (Article.status, status),
        ]:
            if value:
                query = query.where(field == value)
        if batch_id:
            saved_targets = select(ListeningCandidate.article_id).where(
                ListeningCandidate.batch_id == batch_id,
                ListeningCandidate.state == "saved",
                ListeningCandidate.removed.is_(False),
                ListeningCandidate.article_id.is_not(None),
            )
            query = query.where((Article.batch_id == batch_id) | Article.id.in_(saved_targets))
        if q.strip():
            query = query.where(
                Article.payload["title_zh"].as_string().contains(q.strip(), autoescape=True)
                | Article.payload["title_en"].as_string().contains(q.strip(), autoescape=True)
            )
        return page_view(
            db,
            query.order_by(Article.created_at.desc(), Article.id),
            page,
            limit,
            lambda r: service.article_view(db, r),
        )

    @router.post("/articles", response_model=C.Article)
    def add_article(
        body: C.ArticleInput,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        now = request.app.state.clock()

        def execute():
            row = service.create_article(db, body.topic_id, body.payload.model_dump(), now)
            service.audit(db, admin.id, "article.create", now)
            return service.article_view(db, row)

        return operate(
            db, admin, "admin", key, "listening.article.create", body.model_dump(), now, execute
        )

    @router.post("/articles/batch-delete", response_model=C.BatchDeleteResult)
    def batch_delete(
        body: C.BatchDelete,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        return batch_action(db, admin, key, body, "delete", request.app.state.clock())

    @router.post("/articles/batch-offline", response_model=C.BatchDeleteResult)
    def batch_offline(
        body: C.BatchDelete,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        return batch_action(db, admin, key, body, "offline", request.app.state.clock())

    @router.post("/articles/batch-publish", response_model=C.BatchPublishResult)
    def batch_publish(
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
                        row = service.require_article(db, item.id, item.revision, lock=True)
                        result = service.publish_article(
                            db,
                            request.app.state.settings,
                            admin.id,
                            row,
                            C.PublishInput(revision=item.revision),
                            request.app.state.clock(),
                        )
                    results.append(
                        {
                            "id": item.id,
                            "status": "success",
                            "published_version_id": result["version_id"],
                            "revision": result["revision"],
                        }
                    )
                except DomainError as error:
                    results.append({"id": item.id, "status": "failed", "error": error.code})
            service.audit(db, admin.id, "articles.batch_publish", request.app.state.clock())
            return {"items": results}

        return operate(
            db,
            admin,
            "admin",
            key,
            "listening.batch.publish",
            body.model_dump(),
            request.app.state.clock(),
            execute,
        )

    @router.get("/articles/{article_id}", response_model=C.Article)
    def read_article(
        article_id: str,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        return service.article_view(db, service.require_article(db, article_id, allow_deleted=True))

    @router.put("/articles/{article_id}", response_model=C.Article)
    def edit_article(
        article_id: str,
        body: C.ArticleUpdate,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        def execute():
            service.catalog_lock(db)
            row = service.require_article(db, article_id, body.revision, lock=True)
            service.audit(db, admin.id, "article.update", request.app.state.clock())
            return service.update_article(db, row, body, request.app.state.clock())

        return operate(
            db,
            admin,
            "admin",
            key,
            "listening.article.update:" + article_id,
            body.model_dump(),
            request.app.state.clock(),
            execute,
        )

    @router.post("/articles/{article_id}/preview", response_model=C.ArticlePreview)
    def preview(
        article_id: str,
        body: C.Revision,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        return operate(
            db,
            admin,
            "admin",
            key,
            "listening.preview:" + article_id,
            body.model_dump(),
            request.app.state.clock(),
            lambda: service.preview_article(
                db,
                request.app.state.settings,
                admin.id,
                service.require_article(db, article_id, body.revision),
                request.app.state.clock(),
            ),
        )

    @router.post("/articles/{article_id}/publish", response_model=C.Article)
    def publish(
        article_id: str,
        body: C.PublishInput,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        def execute():
            service.catalog_lock(db)
            row = service.require_article(db, article_id, body.revision, lock=True)
            result = service.publish_article(
                db, request.app.state.settings, admin.id, row, body, request.app.state.clock()
            )
            service.audit(db, admin.id, "article.publish", request.app.state.clock())
            return result

        return operate(
            db,
            admin,
            "admin",
            key,
            "listening.publish:" + article_id,
            body.model_dump(),
            request.app.state.clock(),
            execute,
        )

    @router.post("/articles/{article_id}/offline", response_model=C.Article)
    def offline(
        article_id: str,
        body: C.Revision,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        return single_action(db, admin, key, article_id, body, "offline", request.app.state.clock())

    @router.post("/articles/{article_id}/delete", response_model=C.Article)
    def delete(
        article_id: str,
        body: C.Revision,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        return single_action(db, admin, key, article_id, body, "delete", request.app.state.clock())

    @router.get("/order", response_model=C.OrderResult)
    def order(
        scope: Literal["global", "topic"],
        topic_id: str | None = None,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        return service.order_view(db, scope, topic_id)

    @router.put("/order", response_model=C.OrderResult)
    def save_order(
        body: C.OrderInput,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        def execute():
            service.catalog_lock(db)
            before = service.order_view(db, body.scope, body.topic_id)
            before = {
                **before,
                "scope": body.scope,
                "topic_id": body.topic_id,
                "policy": service.policy_view(db),
            }
            result = service.save_order(db, body)
            service.configuration_history(
                db,
                admin.id,
                "order",
                before,
                {
                    **result,
                    "scope": body.scope,
                    "topic_id": body.topic_id,
                    "policy": service.policy_view(db),
                },
                request.app.state.clock(),
            )
            service.audit(db, admin.id, "order.save", request.app.state.clock())
            return {
                **result,
                "audit": {
                    "admin_id": admin.id,
                    "occurred_at": timestamp(request.app.state.clock()),
                    "scope": body.scope,
                    "topic_id": body.topic_id,
                    "before": before,
                    "after": result,
                },
            }

        return operate(
            db,
            admin,
            "admin",
            key,
            "listening.order.save",
            body.model_dump(),
            request.app.state.clock(),
            execute,
        )

    @router.get("/free-policy", response_model=C.FreePolicy)
    def free_policy(
        admin=Depends(administrator), db: Session = Depends(database, scope="function")
    ):
        return service.policy_view(db)

    @router.post("/free-policy/preview", response_model=C.FreePreview)
    def free_preview(
        body: C.FreeCount,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        return operate(
            db,
            admin,
            "admin",
            key,
            "listening.free.preview",
            body.model_dump(),
            request.app.state.clock(),
            lambda: service.free_preview(
                db, request.app.state.settings, admin.id, body.free_count, request.app.state.clock()
            ),
        )

    @router.put("/free-policy", response_model=C.FreePolicy)
    def free_save(
        body: C.FreePolicyUpdate | C.Confirmation,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        def execute():
            service.catalog_lock(db)
            before = service.policy_view(db)
            if isinstance(body, C.FreePolicyUpdate):
                result = service.save_free_count(db, body.free_count, body.revision)
            else:
                result = service.save_free(
                    db,
                    request.app.state.settings,
                    admin.id,
                    body.preview_token,
                    request.app.state.clock(),
                )
            service.configuration_history(
                db, admin.id, "free-policy", before, result, request.app.state.clock()
            )
            service.audit(db, admin.id, "free.save", request.app.state.clock())
            return {
                **result,
                "audit": {
                    "admin_id": admin.id,
                    "occurred_at": timestamp(request.app.state.clock()),
                    "before": before,
                    "after": result,
                },
            }

        return operate(
            db,
            admin,
            "admin",
            key,
            "listening.free.save",
            body.model_dump(),
            request.app.state.clock(),
            execute,
        )

    @router.post("/articles/{article_id}/media", response_model=MediaMetadata)
    def upload(
        article_id: str,
        request: Request,
        kind: Literal["audio", "image"],
        file: UploadFile = File(...),
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        limit = (
            (
                request.app.state.settings.audio_limit_mb
                if kind == "audio"
                else request.app.state.settings.image_limit_mb
            )
            * 1024
            * 1024
        )
        data = file.file.read(limit + 1)

        def execute():
            service.catalog_lock(db)
            service.require_article(db, article_id)
            return media.view(
                media.save_media(
                    db,
                    request.app.state.settings,
                    article_id,
                    kind,
                    data,
                    file.filename or "",
                    request.app.state.clock(),
                )
            )

        return operate(
            db,
            admin,
            "admin",
            key,
            "listening.media.upload:" + article_id,
            {"kind": kind, "sha256": __import__("hashlib").sha256(data).hexdigest()},
            request.app.state.clock(),
            execute,
        )

    @router.get("/articles/{article_id}/media/{media_id}")
    def read_media(
        article_id: str,
        media_id: str,
        request: Request,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        row = service.require_article(db, article_id)
        medium = db.get(Media, media_id)
        if (
            not medium
            or medium.owner_kind != "listening"
            or (
                medium.owner_id not in {row.id, row.batch_id}
                and medium.id not in service.imported_media_ids(db, row)
            )
            or medium.state != "ready"
        ):
            raise DomainError(404, "listening_media_missing", "素材不可用")
        from .media_api import playback_medium

        return deliver(playback_medium(db, medium), request)

    @router.get("/articles/{article_id}/published", response_model=C.Article)
    def published_article(
        article_id: str,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        """Read the active publication for administrator history without learner mutations."""
        row, version = service.admin_publication(db, article_id)
        return service.published_article_view(db, row, version)

    @router.get("/articles/{article_id}/published/media/{media_id}")
    @router.head("/articles/{article_id}/published/media/{media_id}", include_in_schema=False)
    def published_media(
        article_id: str,
        media_id: str,
        request: Request,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        """Stream only media referenced by the article's current effective publication."""
        _, version = service.admin_publication(db, article_id)
        return deliver(media.controlled_media(db, version.payload, media_id), request)

    @router.get("/articles/{article_id}/timeline", response_model=C.Timeline)
    def timeline(
        article_id: str,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        return timeline_view(db, service.require_article(db, article_id).payload)

    @router.post("/articles/{article_id}/timeline/retry", response_model=C.Timeline)
    def timeline_retry(
        article_id: str,
        body: C.Revision,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        return timeline_change(db, admin, key, article_id, body, "retry", request)

    @router.post("/articles/{article_id}/timeline/review", response_model=C.Timeline)
    def timeline_review(
        article_id: str,
        body: C.Revision,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        return timeline_change(db, admin, key, article_id, body, "review", request)

    @router.put("/articles/{article_id}/timeline", response_model=C.Timeline)
    def timeline_upload(
        article_id: str,
        body: C.TimelineInput,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        return timeline_change(db, admin, key, article_id, body, "upload", request)

    @router.get("/users/{user_id}/records", response_model=Page[C.Summary])
    def user_records(
        user_id: str,
        request: Request,
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=50),
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        if not db.get(User, user_id):
            raise DomainError(404, "user_missing", "用户不存在")
        return personal_page(
            db, user_id, "records", request.app.state.clock(), page, limit, include_deleted=True
        )

    @router.get("/users/{user_id}/checkins/{day}", response_model=C.MixedDay)
    def user_checkin(
        user_id: str,
        day: date,
        request: Request,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        if not db.get(User, user_id):
            raise DomainError(404, "user_missing", "用户不存在")
        return mixed_day(db, user_id, day, request.app.state.clock())

    return router


def single_action(db, admin, key, article_id, body, action, now):
    def execute():
        service.catalog_lock(db)
        row = service.require_article(db, article_id, body.revision, lock=True)
        result = service.lifecycle(db, row, action, now)
        service.audit(db, admin.id, "article." + action, now)
        return result

    return operate(
        db,
        admin,
        "admin",
        key,
        "listening." + action + ":" + article_id,
        body.model_dump(),
        now,
        execute,
    )


def batch_action(db, admin, key, body, action, now):
    def execute():
        service.catalog_lock(db)
        results = []
        for item in body.items:
            try:
                with db.begin_nested():
                    row = service.require_article(db, item.id, item.revision, lock=True)
                    service.lifecycle(db, row, action, now)
                results.append({"id": item.id, "status": "success"})
            except DomainError as error:
                results.append({"id": item.id, "status": "failed", "error": error.code})
        service.audit(db, admin.id, "articles.batch_" + action, now)
        return {"items": results}

    return operate(
        db, admin, "admin", key, "listening.batch." + action, body.model_dump(), now, execute
    )


def mutate_timeline(db, admin, payload, body, action, request):
    now = request.app.state.clock()
    current = timeline_view(db, payload)
    row = (
        db.scalar(
            select(ListeningTimeline)
            .where(ListeningTimeline.input_hash == current["input_hash"])
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if current["input_hash"]
        else None
    )
    if not row:
        raise DomainError(422, "listening_timeline_inputs_missing", "请先保存有效正文与就绪音频")
    if action == "review":
        row.reviewed_at, row.reviewed_by = now, admin.id
    elif action == "retry":
        if row.state in {"failed", "needs_attention"}:
            if row.error_code == "asr_submission_unknown":
                raise DomainError(
                    409, "asr_result_unknown", "识别提交结果未知，请先由运维核查服务商任务"
                )
            job = ListeningJob(
                input_hash=row.input_hash, state="pending", created_at=now, updated_at=now
            )
            db.add(job)
            db.flush()
            row.job_id, row.state, row.error_code = job.id, "pending", None
    else:
        if body.input_hash != row.input_hash:
            raise DomainError(409, "listening_timeline_changed", "正文音频已变化，请重新核对")
        settings = request.app.state.settings
        audio = db.get(Media, row.audio_id)
        words = [w.model_dump() for w in body.words]
        validate_words(
            row.body_en,
            words,
            round(audio.duration * 1000),
            minimum_coverage=settings.listening_alignment_minimum_coverage,
            max_word_ms=settings.listening_alignment_max_word_ms,
        )
        old_job = db.get(ListeningJob, row.job_id) if row.job_id else None
        if old_job:
            old_job.state = "superseded"
        row.job_id, row.words, row.state, row.error_code = None, words, "ready", None
    service.audit(db, admin.id, "timeline." + action, now)
    db.flush()
    return timeline_view(db, payload)


def timeline_change(db, admin, key, article_id, body, action, request):
    now = request.app.state.clock()

    def execute():
        service.catalog_lock(db)
        article = service.require_article(db, article_id, body.revision, lock=True)
        return mutate_timeline(db, admin, article.payload, body, action, request)

    return operate(
        db,
        admin,
        "admin",
        key,
        f"listening.timeline.{action}:{article_id}",
        body.model_dump(),
        now,
        execute,
    )


def personal_page(db, user_id, kind, now, page, limit, *, include_deleted=False):
    """Filter learner collections before totals/pagination while keeping admin history readable."""
    model = Favorite if kind == "favorites" else Completion
    query = select(model).where(model.user_id == user_id)
    if not include_deleted:
        query = query.join(Article, model.article_id == Article.id).where(
            Article.deleted_at.is_(None)
        )
    query = (
        query.order_by(Favorite.created_at.desc(), Favorite.article_id)
        if kind == "favorites"
        else query.order_by(Completion.last_completed_at.desc(), Completion.article_id)
    )

    def render(record):
        row = db.get(Article, record.article_id)
        result = service.summary(db, row, user_id, now)
        if kind == "favorites":
            result["favorited_at"] = timestamp(record.created_at)
        if kind != "favorites":
            result.update(
                first_completed_at=timestamp(record.first_completed_at),
                last_completed_at=timestamp(record.last_completed_at),
            )
        return result

    return page_view(db, query, page, limit, render)


def mixed_day(db, user_id, day, now):
    scenes = day_records(db, user_id, day)["items"]
    rows = list(
        db.scalars(
            select(Daily)
            .join(Article, Daily.article_id == Article.id)
            .where(Daily.user_id == user_id, Daily.date == day, Article.deleted_at.is_(None))
            .order_by(Daily.accepted_at.desc(), Daily.article_id)
        )
    )
    articles = [
        {
            **service.summary(db, db.get(Article, row.article_id), user_id, now),
            "completed_at": timestamp(row.accepted_at),
        }
        for row in rows
    ]
    from .learning_models import DailyLearning

    return {
        "date": day.isoformat(),
        "scene_items": scenes,
        "article_items": articles,
        "card_count": db.scalar(
            select(func.count())
            .select_from(DailyLearning)
            .where(DailyLearning.user_id == user_id, DailyLearning.date == day)
        )
        or 0,
        "article_count": db.scalar(
            select(func.count())
            .select_from(Daily)
            .where(Daily.user_id == user_id, Daily.date == day)
        )
        or 0,
    }


def token_target(db, settings, article_id, user_id, ref, now):
    _, version = service.published(db, user_id, article_id, now, ref.version_id, lookup=True)
    payload = version.payload
    selected = next(
        (
            m
            for m in body_tokens(payload["body_en"])
            if m.start() == ref.start and m.end() == ref.end
        ),
        None,
    )
    if not selected:
        raise DomainError(422, "dictionary_reference_invalid", "请选择正文中完整英文词项")
    meanings = [
        w
        for w in payload.get("word_meanings", [])
        if w["start"] == ref.start and w["end"] == ref.end and w["word"] == selected.group()
    ]
    context = (
        {
            "english": selected.group(),
            "meaning": meanings[0]["chinese"],
            "phonetic": meanings[0].get("phonetic", ""),
            "lemma": meanings[0].get("lemma"),
        }
        if len(meanings) == 1
        else None
    )
    config = configuration(settings)
    word = selected.group()
    return TokenTarget(
        word,
        context,
        word,
        config,
        fingerprint({"spelling": word, "reading": word, "configuration": config}),
    )


def mini_routes():
    router = APIRouter(prefix="/api/mini/v1/listening", tags=["thematic listening"])

    @router.get("/home", response_model=C.Home)
    def home(
        request: Request, user=Depends(learner), db: Session = Depends(database, scope="function")
    ):
        now = request.app.state.clock()
        from .access_service import free_ids, policy

        scene_policy = policy(db)
        listening_policy = service.policy_view(db)
        topics = service.topics(db, user.id, now)
        ids = {t["category_id"] for t in topics}
        categories = [
            row_view(c)
            for c in db.scalars(
                select(Category)
                .where(Category.id.in_(ids))
                .order_by(Category.sort_order, Category.id)
            )
        ]
        target = service.continue_row(db, user.id, now)
        return {
            "categories": categories,
            "topics": topics,
            "continue_learning": service.summary(db, target, user.id, now, include_progress=True)
            if target
            else None,
            "configured": service.policy_view(db)["configured"],
            "authorization": authorization(db, user.id, now),
            "free_count": listening_policy["free_count"],
            "actual_free_count": len(listening_policy["article_ids"]),
            "scene_free_count": scene_policy["free_count"],
            "scene_actual_free_count": len(free_ids(db, scene_policy["free_count"])),
            "statistics": statistics(db, user.id, now),
        }

    @router.get("/topics", response_model=dict[str, list[C.TopicProgress]])
    def topics(
        request: Request,
        category_id: str | None = None,
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        return {"items": service.topics(db, user.id, request.app.state.clock(), category_id)}

    @router.get("/topics/{topic_id}/articles", response_model=Page[C.Summary])
    def articles(
        topic_id: str,
        request: Request,
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=50),
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        service.require_topic(db, topic_id)
        query = (
            select(Article)
            .where(
                Article.topic_id == topic_id,
                Article.status == "published",
                Article.deleted_at.is_(None),
            )
            .order_by(Article.topic_order, Article.id)
        )
        return page_view(
            db,
            query,
            page,
            limit,
            lambda r: service.summary(db, r, user.id, request.app.state.clock()),
        )

    @router.get("/favorites", response_model=Page[C.Summary])
    def favorites(
        request: Request,
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=50),
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        return personal_page(db, user.id, "favorites", request.app.state.clock(), page, limit)

    @router.get("/records", response_model=Page[C.Summary])
    def records(
        request: Request,
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=50),
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        return personal_page(db, user.id, "records", request.app.state.clock(), page, limit)

    @router.get("/statistics", response_model=Statistics)
    def stats(
        request: Request, user=Depends(learner), db: Session = Depends(database, scope="function")
    ):
        return statistics(db, user.id, request.app.state.clock())

    @router.get("/checkins", response_model=Page[C.ListeningCheckin])
    def checkins(
        request: Request,
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=50),
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        def render(row):
            from .learning_models import DailyLearning

            return {
                "date": row.date.isoformat(),
                "card_count": db.scalar(
                    select(func.count())
                    .select_from(DailyLearning)
                    .where(DailyLearning.user_id == user.id, DailyLearning.date == row.date)
                )
                or 0,
                "article_count": db.scalar(
                    select(func.count())
                    .select_from(Daily)
                    .where(Daily.user_id == user.id, Daily.date == row.date)
                )
                or 0,
            }

        return page_view(
            db,
            select(Checkin).where(Checkin.user_id == user.id).order_by(Checkin.date.desc()),
            page,
            limit,
            render,
        )

    @router.get("/checkins/{day}", response_model=C.MixedDay)
    def checkin_day(
        day: date,
        request: Request,
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        return mixed_day(db, user.id, day, request.app.state.clock())

    @router.get("/articles/{article_id}/summary", response_model=C.Summary)
    def summary(
        article_id: str,
        request: Request,
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        row = service.require_article(db, article_id, allow_deleted=True)
        if (
            row.status != "published"
            and not db.get(Favorite, (user.id, row.id))
            and not db.get(Completion, (user.id, row.id))
        ):
            raise DomainError(404, "listening_article_missing", "未找到本人可见文章")
        return service.summary(db, row, user.id, request.app.state.clock())

    @router.get("/articles/{article_id}", response_model=C.ArticleDetail)
    def detail(
        article_id: str,
        request: Request,
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        now = request.app.state.clock()
        row, version = service.published(db, user.id, article_id, now)
        audio = db.get(Media, version.payload["audio_id"])
        if not audio or audio.state != "ready" or not audio.duration:
            raise DomainError(503, "listening_audio_unavailable", "完整音频暂不可用，请重试")
        return {
            **service.summary(db, row, user.id, now),
            "payload": version.payload,
            "progress": service.progress_view(db, user.id, row),
            "audio_duration": audio.duration,
            "timeline": timeline_view(db, version.payload),
            "queue_token": service.queue_token(db, request.app.state.settings, user.id, row, now),
        }

    @router.get("/articles/{article_id}/next", response_model=C.NextArticle)
    def next_article(
        article_id: str,
        request: Request,
        queue_token: str | None = None,
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        now = request.app.state.clock()
        row = service.require_article(db, article_id, allow_deleted=True)
        snapshot = None
        if queue_token:
            data = read_preview(
                request.app.state.settings, queue_token, user.id, "listening.next", now
            )
            if data["topic_id"] != row.topic_id or row.id not in data["ids"]:
                raise DomainError(409, "listening_queue_changed", "文章所属主题已变化，请重新进入")
            snapshot = data["ids"]
        target = service.next_row(db, user.id, row, now, snapshot=snapshot)
        return {
            "article": service.summary(db, target, user.id, now, include_progress=True)
            if target
            else None,
            "ended": target is None,
        }

    @router.put("/articles/{article_id}/progress", response_model=C.Progress)
    def progress(
        article_id: str,
        body: C.ProgressInput,
        request: Request,
        user=Depends(learner),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        def execute():
            row, version = service.published(
                db, user.id, article_id, request.app.state.clock(), body.version_id, lock=True
            )
            return service.save_progress(db, user.id, row, version, body, request.app.state.clock())

        return operate(
            db,
            user,
            "mini",
            key,
            "listening.progress:" + article_id,
            body.model_dump(),
            request.app.state.clock(),
            execute,
        )

    @router.post("/articles/{article_id}/complete", response_model=C.ListeningCompletionResult)
    def complete(
        article_id: str,
        body: C.VersionInput,
        request: Request,
        user=Depends(learner),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        return operate(
            db,
            user,
            "mini",
            key,
            "listening.complete:" + article_id,
            body.model_dump(),
            request.app.state.clock(),
            lambda: service.complete(
                db, user, article_id, body.version_id, request.app.state.clock()
            ),
        )

    @router.put("/articles/{article_id}/favorite", response_model=C.FavoriteResult)
    def favorite(
        article_id: str,
        body: C.VersionInput,
        request: Request,
        user=Depends(learner),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        def execute():
            service.published(
                db, user.id, article_id, request.app.state.clock(), body.version_id, lock=True
            )
            if not db.get(Favorite, (user.id, article_id)):
                db.add(
                    Favorite(
                        user_id=user.id, article_id=article_id, created_at=request.app.state.clock()
                    )
                )
            return {"article_id": article_id, "favorite": True}

        return operate(
            db,
            user,
            "mini",
            key,
            "listening.favorite:" + article_id,
            body.model_dump(),
            request.app.state.clock(),
            execute,
        )

    @router.delete("/favorites/{article_id}", response_model=C.FavoriteResult)
    def unfavorite(
        article_id: str,
        request: Request,
        user=Depends(learner),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        def execute():
            row = db.get(Favorite, (user.id, article_id))
            if row:
                db.delete(row)
            return {"article_id": article_id, "favorite": False}

        return operate(
            db,
            user,
            "mini",
            key,
            "listening.unfavorite:" + article_id,
            {},
            request.app.state.clock(),
            execute,
        )

    @router.get("/articles/{article_id}/media/{media_id}")
    @router.head("/articles/{article_id}/media/{media_id}", include_in_schema=False)
    def read_media(
        article_id: str,
        media_id: str,
        version_id: str,
        request: Request,
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        _, version = service.published(
            db, user.id, article_id, request.app.state.clock(), version_id
        )
        return deliver(media.controlled_media(db, version.payload, media_id), request)

    @router.get("/articles/{article_id}/thumbnail")
    def thumbnail(
        article_id: str,
        version_id: str,
        request: Request,
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        version = service.thumbnail_version(db, article_id, version_id)
        return deliver(media.controlled_media(db, version.payload, "", thumbnail=True), request)

    @router.get("/articles/{article_id}/thumbnail-ticket", response_model=C.TicketResult)
    def thumbnail_ticket(
        article_id: str,
        version_id: str,
        request: Request,
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        version = service.thumbnail_version(db, article_id, version_id)
        media.controlled_media(db, version.payload, "", thumbnail=True)
        return media.issue_ticket(request, user.id, article_id, version_id, "", purpose="thumbnail")

    @router.post("/articles/{article_id}/media-ticket", response_model=C.TicketResult)
    def media_ticket(
        article_id: str,
        body: C.MediaTicketInput,
        request: Request,
        user=Depends(learner),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        _, version = service.published(
            db, user.id, article_id, request.app.state.clock(), body.version_id
        )
        media.controlled_media(db, version.payload, body.media_id)
        # No durable mutation: credential refresh must remain short-lived even for receipt replay.
        return media.issue_ticket(request, user.id, article_id, body.version_id, body.media_id)

    @router.get("/media/{credential}")
    @router.head("/media/{credential}", include_in_schema=False)
    def ticket_media(
        credential: str, request: Request, db: Session = Depends(database, scope="function")
    ):
        data = media.read_ticket(db, request, credential)
        if data["purpose"] == "listening:speech":
            ref = C.ListeningDictionaryReference.model_validate(data["reference"])
            target = token_target(
                db,
                request.app.state.settings,
                data["article_id"],
                data["user_id"],
                ref,
                request.app.state.clock(),
            )
            cache = db.get(Pronunciation, target.cache_key)
            medium = db.get(Media, cache.media_id) if cache and cache.media_id else None
            if not medium or status(db, target.cache_key)["state"] != "ready":
                raise DomainError(404, "speech_missing", "发音暂不可用")
            return deliver(medium, request)
        if data["purpose"] == "listening:thumbnail":
            version = service.thumbnail_version(db, data["article_id"], data["version_id"])
            return deliver(media.controlled_media(db, version.payload, "", thumbnail=True), request)
        _, version = service.published(
            db, data["user_id"], data["article_id"], request.app.state.clock(), data["version_id"]
        )
        return deliver(media.controlled_media(db, version.payload, data["media_id"]), request)

    @router.get("/articles/{article_id}/dictionary", response_model=DictionaryResult)
    def dictionary(
        article_id: str,
        ref: Annotated[C.ListeningDictionaryReference, Query()],
        request: Request,
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        target = token_target(
            db, request.app.state.settings, article_id, user.id, ref, request.app.state.clock()
        )
        result = lookup(target, request.app.state.dictionary)
        if target.context and target.context.get("lemma"):
            result = result.model_copy(update={"lemma": target.context["lemma"]})
        return result

    @router.post("/articles/{article_id}/dictionary/pronunciation", response_model=SpeechState)
    def pronunciation(
        article_id: str,
        body: C.ListeningDictionaryReference,
        request: Request,
        user=Depends(learner),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        target = token_target(
            db, request.app.state.settings, article_id, user.id, body, request.app.state.clock()
        )
        value = operate(
            db,
            user,
            "mini",
            key,
            "listening.speech:" + article_id,
            body.model_dump(),
            request.app.state.clock(),
            lambda: request_speech(
                db,
                request.app.state.settings,
                user,
                "mini",
                {"english": target.word},
                target.reading,
                target.config,
                target.cache_key,
                request.app.state.clock(),
            ),
        )
        return speech_grant(value, request, user.id, article_id, body)

    @router.get("/articles/{article_id}/dictionary/pronunciation", response_model=SpeechState)
    def read_pronunciation(
        article_id: str,
        ref: Annotated[C.ListeningDictionaryReference, Query()],
        request: Request,
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        target = token_target(
            db, request.app.state.settings, article_id, user.id, ref, request.app.state.clock()
        )
        return speech_grant(status(db, target.cache_key), request, user.id, article_id, ref)

    return router


def speech_grant(value, request, user_id, article_id, ref):
    if value["state"] != "ready":
        return value
    import json

    from .security import decrypt, encrypt

    ticket = media.issue_ticket(request, user_id, article_id, ref.version_id, "", purpose="speech")
    credential = ticket["url"].rsplit("/", 1)[1]
    payload = json.loads(decrypt(request.app.state.settings, credential) or "{}")
    payload["reference"] = ref.model_dump()
    return {
        **value,
        "url": "/api/mini/v1/listening/media/"
        + encrypt(request.app.state.settings, json.dumps(payload)),
    }
