"""Fail-closed published agreements and account-scoped permission transitions."""

import json

from sqlalchemy import select

from .database import naive_utc, timestamp
from .errors import DomainError
from .models import Consent
from .persistence import insert_once
from .privacy_models import AnalyticsPreference


def load_documents(settings):
    """Read only explicitly configured complete policy documents; malformed files fail closed."""
    try:
        values = (
            json.loads(settings.privacy_documents_path.read_text())
            if settings.privacy_documents_path
            else []
        )
        return checked_documents(values)
    except (OSError, ValueError, TypeError):
        return []


def checked_documents(values):
    """Publish necessary agreement pairs only when every required field is usable."""
    if not isinstance(values, list):
        return []
    documents: list[dict[str, str]] = []
    for value in values:
        if not isinstance(value, dict) or value.get("kind") not in {
            "terms",
            "privacy",
            "analytics",
        }:
            return []
        if any(
            not isinstance(value.get(k), str) or not value[k].strip()
            for k in ("version", "title", "content")
        ):
            return []
        if len(value["version"]) > 64 or value["kind"] in {d["kind"] for d in documents}:
            return []
        documents.append({k: value[k] for k in ("kind", "version", "title", "content")})
    return documents if {"terms", "privacy"} <= {v["kind"] for v in documents} else []


def documents(request):
    """Return the current validated publication without inventing fallback legal text."""
    return checked_documents(request.app.state.privacy_documents)


def versions(request):
    """Resolve versions from the actual published documents."""
    return {v["kind"]: v["version"] for v in documents(request)}


def client_transport_ready(request):
    """Keep the incompatible SDK closed regardless of legacy transport configuration."""
    return False


def validate_confirmation(request, confirmation):
    """A new publication cannot be accepted via a legacy boolean or stale version."""
    current = versions(request)
    if not current:
        if confirmation is not None:
            raise DomainError(409, "agreements_unavailable", "正式协议尚未配置")
        return
    if (
        not confirmation
        or confirmation.terms_version != current["terms"]
        or confirmation.privacy_version != current["privacy"]
    ):
        raise DomainError(
            409, "agreement_confirmation_required", "协议已更新，请阅读并确认当前版本"
        )


def save_confirmation(db, user_id, confirmation, now):
    """Attach a specific anonymous confirmation only to the trusted authenticated account."""
    for purpose, version in [
        ("terms", confirmation.terms_version),
        ("privacy", confirmation.privacy_version),
    ]:
        insert_once(
            db,
            Consent,
            dict(
                user_id=user_id,
                purpose=purpose,
                version=version,
                confirmation_id=confirmation.confirmation_id,
                source=confirmation.source,
                client_confirmed_at=naive_utc(confirmation.client_confirmed_at),
                accepted_at=now,
            ),
            ["user_id", "purpose", "confirmation_id"],
        )
        row = db.scalar(
            select(Consent).where(
                Consent.user_id == user_id,
                Consent.purpose == purpose,
                Consent.confirmation_id == confirmation.confirmation_id,
            )
        )
        if (
            row.version != version
            or row.source != confirmation.source
            or row.client_confirmed_at != naive_utc(confirmation.client_confirmed_at)
        ):
            raise DomainError(409, "operation_conflict", "协议确认内容已变化")


def agreement_state(db, request, user_id):
    """Read current account confirmations without inheriting another device's analysis choice."""
    current = versions(request)
    rows = list(
        db.scalars(
            select(Consent)
            .where(Consent.user_id == user_id, Consent.purpose.in_(["terms", "privacy"]))
            .order_by(Consent.accepted_at.desc())
        )
    )
    accepted = {}
    for row in rows:
        if row.purpose not in accepted or row.version == current.get(row.purpose):
            accepted[row.purpose] = dict(
                version=row.version, accepted_at=timestamp(row.accepted_at), source=row.source
            )
    return {
        "current": bool(current)
        and all(accepted.get(k, {}).get("version") == current[k] for k in ("terms", "privacy")),
        "accepted": accepted,
    }


def preference(db, user_id, now, *, lock=False):
    """Reserve then lock the account preference before any concurrent transition."""
    if lock:
        insert_once(
            db,
            AnalyticsPreference,
            dict(user_id=user_id, enabled=False, scope_version="", revision=0, updated_at=now),
            ["user_id"],
        )
    return db.scalar(
        select(AnalyticsPreference).where(AnalyticsPreference.user_id == user_id).with_for_update()
        if lock
        else select(AnalyticsPreference).where(AnalyticsPreference.user_id == user_id)
    )


def preference_view(row, request):
    """An explicit permission and the actual collection state are different facts."""
    enabled = bool(row and row.enabled and row.scope_version == versions(request).get("analytics"))
    return dict(
        enabled=enabled,
        scope_version=row.scope_version if row else "",
        revision=row.revision if row else 0,
        updated_at=timestamp(row.updated_at) if row else None,
        collecting=False,
    )


def change_preference(db, request, user_id, body, now):
    """Use a revision-checked account transition; stale disclosure never creates permission."""
    row = preference(db, user_id, now, lock=True)
    if row.revision != body.expected_revision:
        raise DomainError(409, "analytics_revision_conflict", "统计选择已变化，请核对后重试")
    if body.enabled and (
        versions(request).get("analytics") != body.scope_version
        or not body.scope_version
        or not agreement_state(db, request, user_id)["current"]
    ):
        raise DomainError(409, "analytics_consent_required", "请阅读并确认当前统计披露")
    row.enabled = body.enabled
    row.scope_version = body.scope_version if body.enabled else ""
    row.revision += 1
    row.enabled_at = now if body.enabled else None
    row.updated_at = now
    db.flush()
    return preference_view(row, request)
