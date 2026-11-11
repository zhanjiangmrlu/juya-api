"""One authoritative access decision, independent of login and learning statistics."""

import calendar
import json
from datetime import date, datetime, timedelta

from sqlalchemy import select

from . import learning_features
from .access_models import FreePolicy, LearningAuthorization
from .content_models import Card, SettingCounter
from .database import timestamp
from .errors import DomainError
from .learning_service import business_date, day_bounds
from .security import decrypt, encrypt


def authorization(db, user_id, now):
    """Derive effective status at server time; revocation retains the original dates."""
    row = db.get(LearningAuthorization, user_id) if user_id is not None else None
    status = "none"
    if row and row.expires_on and not row.revoked_at:
        status = "active" if row.expires_on >= business_date(now) else "expired"
    return {
        "status": status,
        "starts_on": row.starts_on.isoformat() if row and row.starts_on else None,
        "expires_on": row.expires_on.isoformat() if row and row.expires_on else None,
        "expires_at": timestamp(day_bounds(row.expires_on)[1]) if row and row.expires_on else None,
        "revision": row.revision if row else 0,
    }


def policy(db):
    """Missing policy means rollout is disabled, never a guessed free quantity."""
    row = db.get(FreePolicy, 1)
    return {
        "enabled": True,
        "free_count": len(free_ids(db)),
        "revision": row.revision if row else 0,
    }


def free_ids(db, count=None):
    """Return the full explicit live set; the old numeric argument no longer selects content."""
    return list(
        db.scalars(
            select(Card.id)
            .where(
                Card.status == "published",
                Card.deleted_at.is_(None),
                Card.current_version_id.is_not(None),
                Card.is_free.is_(True),
            )
            .order_by(Card.sort_order, Card.id)
        )
    )


def learning_access_snapshot(db, user_id, now):
    """Keep shared catalog access inputs in the current read operation only."""
    counter = db.get(SettingCounter, "catalog_revision")
    return authorization(db, user_id, now), counter.value if counter else 0


def learning_access(db, user_id, card_id, now, *, snapshot=None, card=None):
    """Require publication and explicit free access while learning grants are paused."""
    grant, catalog_revision = (
        snapshot if snapshot is not None else learning_access_snapshot(db, user_id, now)
    )
    card = card if card is not None else db.get(Card, card_id)
    published = bool(
        card and not card.deleted_at and card.status == "published" and card.current_version_id
    )
    free = bool(published and card.is_free)
    learn = published and (
        free or (learning_features.LEARNING_AUTHORIZATION_ENABLED and grant["status"] == "active")
    )
    return {
        "can_learn": bool(learn),
        "can_lookup": bool(
            learning_features.IN_APP_DICTIONARY_ENABLED and learn and grant["status"] == "active"
        ),
        "is_free": free,
        "reason": None
        if learn
        else (
            (
                "learning_authorization_required"
                if learning_features.LEARNING_AUTHORIZATION_ENABLED
                else "content_not_open"
            )
            if published
            else "content_unavailable"
        ),
        "version": (
            f"{card.free_revision if card else 0}:{grant['revision']}:"
            f"{catalog_revision}:{grant['status']}:{learning_features.permission_mode()}"
        ),
        "server_now": timestamp(now),
        "expires_at": grant["expires_at"]
        if learning_features.LEARNING_AUTHORIZATION_ENABLED
        else None,
    }


def require_access(db, user_id, card_id, now, *, lookup=False, lock=False):
    """Fence controlled operations, with catalog-before-card ordering for writes."""
    if lock:
        db.scalar(
            select(SettingCounter)
            .where(SettingCounter.name == "catalog_revision")
            .with_for_update(read=True)
            .execution_options(populate_existing=True)
        )
    now = db.info.get("clock", lambda: now)()
    result = learning_access(db, user_id, card_id, now)
    if result["reason"] == "content_unavailable":
        from .content_service import published_card

        published_card(db, card_id)
    if not result["can_lookup" if lookup else "can_learn"]:
        code = (
            (
                "lookup_authorization_required"
                if learning_features.IN_APP_DICTIONARY_ENABLED
                else "lookup_unavailable"
            )
            if lookup
            else result["reason"]
        )
        raise DomainError(
            403,
            code,
            "暂未开放"
            if code in {"lookup_unavailable", "content_not_open"}
            else ("点词查询需学习授权" if lookup else "此场景需学习授权"),
        )
    return result


def add_month(day):
    """Advance one calendar month, clamping January31 to the true February end."""
    year, month = (day.year + 1, 1) if day.month == 12 else (day.year, day.month + 1)
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def proposed_authorization(db, user_id, action, expires_on, now):
    """Validate state transitions and compute a confirmation-bound final date."""
    current = authorization(db, user_id, now)
    today = business_date(now)
    active = current["status"] == "active"
    if action in {"renew", "revoke"} and not active:
        raise DomainError(409, "authorization_changed", "当前无有效授权，请重新核对后开通")
    if action == "grant" and active:
        raise DomainError(409, "authorization_changed", "当前授权有效，请使用续期")
    if action == "set_expiry":
        if not expires_on or expires_on < today:
            raise DomainError(422, "expiry_invalid", "请选择今天或未来的到期日")
        end = expires_on
    elif action in {"grant", "renew"}:
        end = add_month(date.fromisoformat(current["expires_on"]) if active else today)
    else:
        end = date.fromisoformat(current["expires_on"]) if current["expires_on"] else None
    start = date.fromisoformat(current["starts_on"]) if active and current["starts_on"] else today
    return {
        "starts_on": start.isoformat(),
        "expires_on": end.isoformat() if end else None,
        "status": "none" if action == "revoke" else "active",
    }


def preview_token(settings, admin_id, purpose, values, now):
    """Seal a short-lived confirmation snapshot; clients cannot forge its contents."""
    return encrypt(
        settings,
        json.dumps(
            {
                "admin_id": admin_id,
                "purpose": purpose,
                "expires": (now + timedelta(minutes=15)).isoformat(),
                **values,
            }
        ),
    )


def read_preview(settings, value, admin_id, purpose, now):
    """Reject wrong actor, purpose, malformed or expired confirmation before mutation."""
    try:
        data = json.loads(decrypt(settings, value) or "{}")
        valid = (
            data["admin_id"] == admin_id
            and data["purpose"] == purpose
            and datetime.fromisoformat(data["expires"]) > now
        )
    except Exception:
        valid, data = False, {}
    if not valid:
        raise DomainError(409, "access_preview_expired", "核对结果已失效，请重新核对")
    return data


def access_context(db, user_id, now):
    """Return the caller's grant and policy from one response context."""
    return {
        **policy(db),
        "authorization": authorization(db, user_id, now),
        "server_now": timestamp(now),
    }


def free_uncompleted(db, user_id):
    """Count the global free set before personal completion filtering."""
    from sqlalchemy import func

    from .learning_models import Completion

    ids = free_ids(db, policy(db)["free_count"])
    return (
        db.scalar(
            select(func.count())
            .select_from(Card)
            .where(
                Card.id.in_(ids),
                Card.id.not_in(select(Completion.card_id).where(Completion.user_id == user_id)),
            )
        )
        or 0
    )
