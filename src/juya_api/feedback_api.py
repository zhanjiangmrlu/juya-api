"""Role-separated private feedback with final safety checks and durable write receipts."""

import hashlib
import json
from datetime import UTC
from typing import Literal

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .content_models import Card
from .content_service import published_card
from .dependencies import (
    administrator,
    database,
    learner,
    operation_key,
    write_transaction,
)
from .errors import DomainError
from .feedback_contracts import (
    AdminMessage,
    CreateFeedback,
    FeedbackDetail,
    FeedbackImage,
    FeedbackPage,
    FeedbackReadReceipt,
    FeedbackStatus,
    FeedbackUnread,
    ReadFeedback,
    UserMessage,
)
from .feedback_models import Feedback, FeedbackRead
from .feedback_models import FeedbackImage as ImageRow
from .feedback_service import (
    append_event,
    audit,
    authorized_image,
    check_images,
    feedback_view,
    image_view,
    normalized_image,
    owned_feedback,
    unread_query,
)
from .models import Administrator, AdminSession, MiniSession, User
from .pronunciation_api import session_digest
from .security import decrypt, encrypt, lookup
from .storage import ObjectStorage
from .transactions import operate, previous_result


def safety(request, method, actor, role, key, action, *content):
    if not request.app.state.settings.feedback_safety_enabled:
        return
    correlation = lookup(
        request.app.state.settings,
        "feedback-safety",
        role + ":" + actor.id + ":" + key + ":" + action,
    )
    try:
        result = getattr(request.app.state.feedback_safety, method)(*content, correlation)
        if result is not None:
            raise ValueError("incomplete safety adapter")
    except DomainError:
        raise
    except Exception:
        raise DomainError(
            503, "content_safety_unavailable", "内容安全检查暂不可用，请保留输入后重试"
        ) from None


def routes(role: Literal["mini", "admin"]):
    router = APIRouter(prefix=f"/api/{role}/v1/feedback", tags=["private feedback"])
    authorize = learner if role == "mini" else administrator
    audit_dependencies = [Depends(write_transaction)] if role == "admin" else []

    @router.get("", response_model=FeedbackPage, dependencies=audit_dependencies)
    def listing(
        request: Request,
        page: int = Query(1, ge=1),
        limit: int = Query(10, ge=1, le=50),
        status: FeedbackStatus | None = None,
        search: str = Query("", max_length=200),
        actor=Depends(authorize),
        db: Session = Depends(database, scope="function"),
    ):
        query = select(Feedback)
        if role == "mini":
            query = query.where(Feedback.user_id == actor.id)
        if status is not None:
            query = query.where(Feedback.status == status)
        query = query.order_by(Feedback.updated_at.desc(), Feedback.id.desc())
        needle = search.strip().casefold() if role == "admin" else ""
        if needle:
            rows, total = [], 0
            for row in db.scalars(query.execution_options(yield_per=100)):
                values = [
                    row.id,
                    row.user_id,
                    row.source_title or "",
                    row.source_title_en,
                    decrypt(request.app.state.settings, row.summary_cipher) or "",
                ]
                if not any(needle in value.casefold() for value in values):
                    continue
                if (page - 1) * limit <= total < page * limit:
                    rows.append(row)
                total += 1
        else:
            total = (
                db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
            )
            rows = list(db.scalars(query.offset((page - 1) * limit).limit(limit)))
        if role == "admin":
            audit(db, actor, "feedback.list", None, request.app.state.clock())
        return {
            "items": [feedback_view(db, row, request, actor, role) for row in rows],
            "total": total,
            "page": page,
            "limit": limit,
        }

    @router.get("/unread", response_model=FeedbackUnread)
    def unread(actor=Depends(authorize), db: Session = Depends(database, scope="function")):
        count = (
            db.scalar(select(func.count()).select_from(unread_query(actor, role).subquery())) or 0
        )
        return {"unread": count > 0, "count": count}

    if role == "mini":

        @router.post("", status_code=201, response_model=FeedbackDetail)
        def create(
            body: CreateFeedback,
            request: Request,
            actor=Depends(learner),
            key: str = Depends(operation_key),
            db: Session = Depends(database, scope="function"),
        ):
            settings = request.app.state.settings
            action, payload = "feedback.create", body.model_dump()
            previous = previous_result(db, actor, role, key, action, payload)
            if previous is not None:
                return previous
            check_images(db, actor.id, body.images)
            if body.source == "scene":
                assert body.card_id is not None
                published_card(db, body.card_id, body.version_id)
            safety(request, "check_text", actor, role, key, action, body.text)

            def execute():
                title, title_en = None, ""
                if body.source == "scene":
                    assert body.card_id is not None
                    db.scalar(
                        select(Card)
                        .where(Card.id == body.card_id)
                        .with_for_update(read=True)
                        .execution_options(populate_existing=True)
                    )
                    _, version = published_card(db, body.card_id, body.version_id)
                    title, title_en = version.payload["name"], version.payload.get("title_en", "")
                now = request.app.state.clock()
                row = Feedback(
                    user_id=actor.id,
                    category=body.category,
                    status="pending",
                    summary_cipher=encrypt(settings, body.text[:120]),
                    source=body.source,
                    card_id=body.card_id,
                    version_id=body.version_id,
                    source_title=title,
                    source_title_en=title_en,
                    created_at=now,
                    updated_at=now,
                )
                db.add(row)
                db.flush()
                append_event(db, settings, row, actor, role, body.text, "pending", body.images, now)
                return feedback_view(db, row, request, actor, role, detail=True)

            return operate(db, actor, role, key, action, payload, request.app.state.clock, execute)

        @router.post("/images", status_code=201, response_model=FeedbackImage)
        def upload(
            request: Request,
            file: UploadFile = File(...),
            actor=Depends(learner),
            key: str = Depends(operation_key),
            db: Session = Depends(database, scope="function"),
        ):
            settings = request.app.state.settings
            maximum = settings.image_limit_mb * 1024 * 1024
            raw = file.file.read(maximum + 1)
            if not raw or len(raw) > maximum:
                raise DomainError(413, "upload_limit", "截图为空或超过当前上传限制")
            action, payload = "feedback.image.upload", {"sha256": hashlib.sha256(raw).hexdigest()}
            previous = previous_result(db, actor, role, key, action, payload)
            if previous is not None:
                return previous
            data, width, height = normalized_image(raw)
            safety(request, "check_image", actor, role, key, action, data, "image/jpeg")

            def execute():
                now = request.app.state.clock()
                image = ImageRow(
                    user_id=actor.id,
                    storage_key="",
                    content_type="image/jpeg",
                    sha256=hashlib.sha256(data).hexdigest(),
                    size=len(data),
                    width=width,
                    height=height,
                    created_at=now,
                )
                # Allocate the immutable server ID before selecting its private object key.
                from .models import identifier

                image.id = identifier()
                image.storage_key = f"{settings.environment}/feedback/{image.id}/{image.sha256}"
                ObjectStorage(settings).put(image.storage_key, data, image.content_type)
                db.add(image)
                db.flush()
                return image_view(image, request, actor, role)

            return operate(db, actor, role, key, action, payload, request.app.state.clock, execute)

    @router.get(
        "/images/{image_id}/url", response_model=FeedbackImage, dependencies=audit_dependencies
    )
    def image_url(
        image_id: str,
        request: Request,
        actor=Depends(authorize),
        db: Session = Depends(database, scope="function"),
    ):
        image = authorized_image(db, image_id, actor, role)
        if role == "admin":
            audit(db, actor, "feedback.image.view", image.feedback_id, request.app.state.clock())
        return image_view(image, request, actor, role)

    @router.head("/images/{credential}", include_in_schema=False, dependencies=audit_dependencies)
    @router.get("/images/{credential}", dependencies=audit_dependencies)
    def image(credential: str, request: Request, db: Session = Depends(database, scope="function")):
        now, settings = request.app.state.clock(), request.app.state.settings
        try:
            payload = json.loads(decrypt(settings, credential) or "{}")
            if (
                not isinstance(payload, dict)
                or payload.get("purpose") != "feedback-image"
                or payload.get("role") != role
                or not isinstance(payload.get("expires"), int)
                or payload["expires"] <= now.replace(tzinfo=UTC).timestamp()
            ):
                raise ValueError("invalid image grant")
        except Exception:
            raise DomainError(
                401, "feedback_image_grant_invalid", "截图地址已失效，请刷新后查看"
            ) from None
        session: MiniSession | AdminSession | None
        if role == "mini":
            session = db.get(MiniSession, payload.get("session", ""))
        else:
            session = db.get(AdminSession, payload.get("session", ""))
        actor_id = getattr(session, "user_id" if role == "mini" else "admin_id", None)
        if not session or session.expires_at <= now or actor_id != payload.get("actor"):
            raise DomainError(401, "feedback_image_session_expired", "请重新登录后查看截图")
        if (role == "admin" or request.headers.get("Authorization")) and payload[
            "session"
        ] != session_digest(request, role):
            raise DomainError(401, "feedback_image_session_expired", "请重新登录后查看截图")
        actor = db.get(User if role == "mini" else Administrator, actor_id)
        if actor is None:
            raise DomainError(401, "feedback_image_session_expired", "请重新登录后查看截图")
        if role == "admin":
            origin = request.headers.get("origin")
            if origin and origin not in settings.allowed_origins:
                raise DomainError(403, "origin_rejected", "请求来源无效")
        row = authorized_image(db, payload.get("image_id"), actor, role)
        if role == "admin":
            audit(db, actor, "feedback.image.view", row.feedback_id, now)
        data = ObjectStorage(settings).read(row.storage_key)
        if len(data) != row.size or hashlib.sha256(data).hexdigest() != row.sha256:
            raise DomainError(503, "feedback_image_unavailable", "截图暂不可用，请重试")
        return Response(
            content=b"" if request.method == "HEAD" else data,
            media_type=row.content_type,
            headers={
                "Cache-Control": "no-store",
                "Content-Length": str(row.size),
                "X-Content-Type-Options": "nosniff",
            },
        )

    @router.get("/{feedback_id}", response_model=FeedbackDetail, dependencies=audit_dependencies)
    def detail(
        feedback_id: str,
        request: Request,
        actor=Depends(authorize),
        db: Session = Depends(database, scope="function"),
    ):
        row = owned_feedback(db, feedback_id, actor, role)
        if role == "admin":
            audit(db, actor, "feedback.view", row.id, request.app.state.clock())
        return feedback_view(db, row, request, actor, role, detail=True)

    @router.put("/{feedback_id}/read", response_model=FeedbackReadReceipt)
    def read(
        feedback_id: str,
        body: ReadFeedback,
        request: Request,
        actor=Depends(authorize),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        def execute():
            row = owned_feedback(db, feedback_id, actor, role, lock=True)
            if body.event_id > row.latest_event_id:
                raise DomainError(422, "feedback_read_invalid", "只能标记本次实际显示的反馈内容")
            cursor = db.get(FeedbackRead, (row.id, role, actor.id))
            if cursor is None:
                cursor = FeedbackRead(
                    feedback_id=row.id, role=role, actor_id=actor.id, event_id=body.event_id
                )
                db.add(cursor)
            else:
                cursor.event_id = max(cursor.event_id, body.event_id)
            db.flush()
            return {"feedback_id": row.id, "read_event_id": cursor.event_id}

        return operate(
            db,
            actor,
            role,
            key,
            f"feedback.{feedback_id}.read",
            body.model_dump(),
            request.app.state.clock,
            execute,
        )

    if role == "mini":

        @router.post("/{feedback_id}/messages", response_model=FeedbackDetail)
        def add_message(
            feedback_id: str,
            body: UserMessage,
            request: Request,
            actor=Depends(learner),
            key: str = Depends(operation_key),
            db: Session = Depends(database, scope="function"),
        ):
            action, payload = f"feedback.{feedback_id}.message", body.model_dump()
            previous = previous_result(db, actor, role, key, action, payload)
            if previous is not None:
                return previous
            owned_feedback(db, feedback_id, actor, role)
            check_images(db, actor.id, body.images)
            safety(request, "check_text", actor, role, key, action, body.text)

            def execute():
                row = owned_feedback(db, feedback_id, actor, role, lock=True)
                now = request.app.state.clock()
                append_event(
                    db,
                    request.app.state.settings,
                    row,
                    actor,
                    role,
                    body.text,
                    "pending",
                    body.images,
                    now,
                )
                return feedback_view(db, row, request, actor, role, detail=True)

            return operate(db, actor, role, key, action, payload, request.app.state.clock, execute)
    else:

        @router.post("/{feedback_id}/messages", response_model=FeedbackDetail)
        def reply(
            feedback_id: str,
            body: AdminMessage,
            request: Request,
            actor=Depends(administrator),
            key: str = Depends(operation_key),
            db: Session = Depends(database, scope="function"),
        ):
            action, payload = f"feedback.{feedback_id}.admin-message", body.model_dump()
            previous = previous_result(db, actor, role, key, action, payload)
            if previous is not None:
                return previous
            owned_feedback(db, feedback_id, actor, role)
            if body.text:
                safety(request, "check_text", actor, role, key, action, body.text)

            def execute():
                row = owned_feedback(db, feedback_id, actor, role, lock=True)
                if (
                    body.expected_latest_event_id is not None
                    and body.expected_latest_event_id != row.latest_event_id
                ):
                    raise DomainError(409, "feedback_changed", "反馈已有新内容，请刷新并核对后重试")
                now = request.app.state.clock()
                append_event(
                    db,
                    request.app.state.settings,
                    row,
                    actor,
                    role,
                    body.text,
                    body.status,
                    [],
                    now,
                )
                audit(db, actor, "feedback.reply", row.id, now)
                return feedback_view(db, row, request, actor, role, detail=True)

            return operate(db, actor, role, key, action, payload, request.app.state.clock, execute)

    return router
