"""Public policy reading and authenticated independent consent management."""

from contextlib import suppress

from fastapi import APIRouter, Depends, Request
from sqlalchemy import event as sql_event
from sqlalchemy.orm import Session

from .access_service import require_access
from .content_models import Operation
from .content_service import published_card
from .database import naive_utc, timestamp
from .dependencies import database, learner, operation_key
from .errors import DomainError
from .privacy_contracts import (
    AgreementConfirmation,
    AgreementState,
    AnalyticsEventInput,
    AnalyticsEventReceiptView,
    AnalyticsPreferenceInput,
    AnalyticsPreferenceView,
    PolicyCatalog,
    PolicyDocument,
    PrivacyState,
)
from .privacy_models import AnalyticsEventReceipt
from .privacy_service import (
    agreement_state,
    change_preference,
    client_transport_ready,
    documents,
    preference,
    preference_view,
    save_confirmation,
    validate_confirmation,
    versions,
)
from .security import digest, fingerprint
from .transactions import actor_lock, operate

PAGE_PATHS = {
    "sub-packages/scenes/detail",
    "sub-packages/account/profile",
    "pages/home/index",
    "sub-packages/account/identity-edit",
    "pages/login/index",
    "pages/favorites/index",
    "sub-packages/feedback/detail",
    "sub-packages/account/policy",
    "sub-packages/account/settings",
    "sub-packages/feedback/create",
    "pages/learning/index",
    "sub-packages/listening/topic",
    "sub-packages/records/index",
    "pages/records/index",
    "sub-packages/feedback/index",
    "sub-packages/listening/article",
    "sub-packages/listening/index",
    "sub-packages/account/contact-edit",
    "pages/profile/index",
    "sub-packages/scenes/image-preview",
}

PROPERTY_KEYS = {"page_path", "content_type", "content_id", "version_id", "audio_kind", "favorite"}


def validate_event(db, request, user, body, now):
    """Validate only necessary references and successful business receipts, never mutate grades."""
    if any(
        k not in PROPERTY_KEYS or isinstance(v, bool) or isinstance(v, str) and len(v) > 128
        for k, v in body.properties.items()
    ):
        raise DomainError(422, "analytics_fields_invalid", "统计事件包含不支持的字段")
    if "audio_kind" in body.properties and body.properties["audio_kind"] not in {"full", "word"}:
        raise DomainError(422, "analytics_fields_invalid", "音频种类无效")
    if "favorite" in body.properties and body.properties["favorite"] not in {0, 1}:
        raise DomainError(422, "analytics_fields_invalid", "收藏结果无效")
    if body.event == "favorite_change" and "favorite" not in body.properties:
        raise DomainError(422, "analytics_fields_invalid", "缺少收藏结果")
    if body.event == "page_enter":
        if set(body.properties) != {"page_path"}:
            raise DomainError(422, "analytics_fields_invalid", "页面事件仅包含页面引用")
        path = body.properties.get("page_path")
        if not isinstance(path, str) or "?" in path or path not in PAGE_PATHS:
            raise DomainError(422, "analytics_fields_invalid", "页面引用无效")
        return
    if "page_path" in body.properties:
        raise DomainError(422, "analytics_fields_invalid", "内容事件不接收页面文本")
    kind, content_id = body.properties.get("content_type"), body.properties.get("content_id")
    if kind not in {"scene", "listening"} or not isinstance(content_id, str):
        raise DomainError(422, "analytics_fields_invalid", "内容引用无效")
    if body.event in {"favorite_change", "learning_complete"}:
        receipt = db.get(Operation, ("mini:" + user.id, digest(body.operation_key or "")))
        verb = (
            "complete"
            if body.event == "learning_complete"
            else ("favorite" if body.properties.get("favorite") == 1 else "unfavorite")
        )
        expected = (
            f"cards.{content_id}.{verb}" if kind == "scene" else f"listening.{verb}:{content_id}"
        )
        permission = preference(db, user.id, now)
        if (
            not receipt
            or receipt.action != expected
            or not permission
            or not permission.enabled_at
            or receipt.accepted_at < permission.enabled_at
        ):
            raise DomainError(
                403, "analytics_business_unconfirmed", "业务成功结果尚未确认或发生在许可之前"
            )
    if kind == "scene":
        require_access(db, user.id, content_id, now)
        published_card(db, content_id, body.properties.get("version_id"))
    else:
        from .listening_service import published

        published(db, user.id, content_id, now, body.properties.get("version_id"))


def routes():
    router = APIRouter(prefix="/api/mini/v1", tags=["协议与可选统计"])

    @router.get(
        "/privacy/policies",
        response_model=PolicyCatalog,
        summary="读取当前公开协议",
        description="匿名读取完整发布的正式协议；材料不全时返回legacy，不虚构正式正文。",
    )
    def policies(request: Request):
        values = documents(request)
        return dict(
            analytics_available=client_transport_ready(request),
            mode="published" if values else "legacy",
            server_now=timestamp(request.app.state.clock()),
            documents=values,
        )

    @router.get(
        "/privacy/policies/{kind}",
        response_model=PolicyDocument,
        summary="读取公开协议正文",
        description="匿名读取指定种类及版本的已发布协议，版本不存在时返回不可用。",
    )
    def policy(kind: str, request: Request, version: str | None = None):
        for value in documents(request):
            if value["kind"] == kind and (version is None or version == value["version"]):
                return value
        raise DomainError(404, "policy_unavailable", "协议正文尚未配置或该版本不可用")

    @router.get(
        "/me/privacy",
        response_model=PrivacyState,
        summary="读取本人协议与统计许可",
        description="按当前可信业务身份返回协议确认及独立统计许可，许可不代表实际采集已运行。",
    )
    def state(
        request: Request, user=Depends(learner), db: Session = Depends(database, scope="function")
    ):
        agreements = agreement_state(db, request, user.id)
        analytics = preference_view(preference(db, user.id, request.app.state.clock()), request)
        if not agreements["current"]:
            analytics["enabled"] = False
            analytics["collecting"] = False
        return dict(agreements=agreements, analytics=analytics)

    @router.post(
        "/me/agreements",
        response_model=AgreementState,
        summary="确认本人当前协议",
        description="版本校验后保存明确确认及来源，确认标识和幂等键防止重复记录。",
    )
    def confirm(
        body: AgreementConfirmation,
        request: Request,
        user=Depends(learner),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        def execute():
            validate_confirmation(request, body)
            save_confirmation(db, user.id, body, request.app.state.clock())
            return agreement_state(db, request, user.id)

        return operate(
            db,
            user,
            "mini",
            key,
            "privacy.confirm",
            body.model_dump(mode="json"),
            request.app.state.clock(),
            execute,
        )

    @router.put(
        "/me/analytics-preference",
        response_model=AnalyticsPreferenceView,
        summary="修改本人可选统计许可",
        description="独立于必要登录，按许可修订号和持久幂等键保存；关闭不要求当前披露版本。",
    )
    def update(
        body: AnalyticsPreferenceInput,
        request: Request,
        user=Depends(learner),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        return operate(
            db,
            user,
            "mini",
            key,
            "privacy.analytics",
            body.model_dump(),
            request.app.state.clock(),
            lambda: change_preference(db, request, user.id, body, request.app.state.clock()),
        )

    @router.post(
        "/analytics/events",
        response_model=AnalyticsEventReceiptView,
        summary="接收已获许可的分析事件",
        description="验证账号许可、五类事件及持久去重，不修改学习成绩。真实统计固定关闭，旧客户端开关不可绕过；仅隔离接收器测试五事件契约。",
    )
    def receive(
        body: AnalyticsEventInput,
        request: Request,
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        receiver = request.app.state.analytics_receiver
        if receiver is None and not client_transport_ready(request):
            raise DomainError(503, "analytics_unavailable", "真实统计尚未启用")
        actor_lock(db, user, "mini")
        now = request.app.state.clock()
        permission = preference(db, user.id, now, lock=True)
        if (
            not permission
            or not permission.enabled
            or permission.revision != body.consent_revision
            or permission.scope_version != versions(request).get("analytics")
            or not agreement_state(db, request, user.id)["current"]
        ):
            raise DomainError(403, "analytics_not_permitted", "当前统计许可不可用")
        occurred = naive_utc(body.occurred_at)
        if not permission.enabled_at or occurred < permission.enabled_at or occurred > now:
            raise DomainError(422, "analytics_time_invalid", "事件不在当前许可时间范围内")
        payload = body.model_dump(mode="json")
        identity = (user.id, body.event_id)
        previous = db.get(AnalyticsEventReceipt, identity)
        request_hash = fingerprint(payload)
        if previous:
            if previous.fingerprint != request_hash:
                raise DomainError(409, "operation_conflict", "事件标识对应内容已变化")
            return {"event_id": body.event_id, "accepted": True}
        validate_event(db, request, user, body, now)
        db.add(
            AnalyticsEventReceipt(
                user_id=user.id,
                event_id=body.event_id,
                fingerprint=request_hash,
                consent_revision=body.consent_revision,
                payload=payload,
                accepted_at=now,
            )
        )
        db.flush()

        def deliver(_db):
            with suppress(Exception):
                receiver(
                    {
                        "user_id": user.id,
                        **{key: value for key, value in payload.items() if key != "operation_key"},
                    }
                )

        if receiver is not None:
            sql_event.listen(db, "after_commit", deliver, once=True)
        return {"event_id": body.event_id, "accepted": True}

    return router
