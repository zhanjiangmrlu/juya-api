"""One learning transaction and one statistical definition for both audiences."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from .content_models import Card, CardVersion, Media
from .content_service import published_card
from .database import timestamp
from .learning_models import Checkin, Completion, DailyLearning, Favorite
from .models import User

BEIJING = ZoneInfo("Asia/Shanghai")


def business_date(now: datetime) -> date:
    """Ignore device dates and use the authoritative server's Beijing natural day."""
    return now.replace(tzinfo=UTC).astimezone(BEIJING).date()


def day_bounds(day: date):
    """Use half-open UTC bounds when filtering stored registration timestamps."""
    begin = datetime.combine(day, time.min, BEIJING).astimezone(UTC).replace(tzinfo=None)
    return begin, begin + timedelta(days=1)


def statistics(db, user_id: str, now: datetime) -> dict:
    """Derive all counters from unique completion and checkin facts, never page visits."""
    today = business_date(now)
    # The writer holds this actor row exclusively. Sharing its lock keeps the
    # following statistical reads at one coherent point under READ COMMITTED.
    db.scalar(select(User.id).where(User.id == user_id).with_for_update(read=True))
    dates = list(
        db.scalars(select(Checkin.date).where(Checkin.user_id == user_id).order_by(Checkin.date))
    )
    current = longest = run = 0
    previous = None
    for day in dates:
        run = run + 1 if previous and day == previous + timedelta(days=1) else 1
        longest = max(longest, run)
        previous = day
    if dates and dates[-1] in {today, today - timedelta(days=1)}:
        current = run
    return {
        "date": today.isoformat(),
        "completed_cards": db.scalar(
            select(func.count()).select_from(Completion).where(Completion.user_id == user_id)
        ),
        "current_streak": current,
        "longest_streak": longest,
        "total_checkin_days": len(dates),
        "checked_in_today": today in dates,
        "today_completed_cards": db.scalar(
            select(func.count())
            .select_from(DailyLearning)
            .where(DailyLearning.user_id == user_id, DailyLearning.date == today)
        ),
        "last_studied_at": timestamp(
            db.scalar(
                select(func.max(Completion.last_completed_at)).where(Completion.user_id == user_id)
            )
        ),
        "favorite_count": db.scalar(
            select(func.count()).select_from(Favorite).where(Favorite.user_id == user_id)
        ),
    }


def card_summary(db, card_id: str) -> dict:
    """Expose only identification metadata when the current card is no longer available."""
    card = db.get(Card, card_id)
    version = (
        db.get(CardVersion, card.current_version_id) if card and card.current_version_id else None
    )
    image = db.get(Media, version.payload["image_id"]) if version else None
    available = bool(card and card.status == "published" and not card.deleted_at and version)
    return {
        "id": card_id,
        "name": version.payload["name"] if version else "场景卡暂不可用",
        "title_en": version.payload.get("title_en", "") if version else "",
        "thumbnail_id": image.thumbnail_id if image else None,
        "available": available,
        "version_id": version.id if version and available else None,
        "unavailable_reason": None
        if available
        else ("deleted" if card and card.deleted_at else "offline"),
    }


def card_state(db, user_id: str, card_id: str, now) -> dict:
    today = business_date(now)
    return {
        "completed": db.get(Completion, (user_id, card_id)) is not None,
        "today_completed": db.get(DailyLearning, (user_id, card_id, today)) is not None,
        "favorite": db.get(Favorite, (user_id, card_id)) is not None,
    }


def complete_learning(db, user, card_id: str, version_id: str, now):
    """Persist completion, daily source and checkin atomically under the actor lock."""
    # Shared record lock orders completion against administrator offline/publish.
    # It permits concurrent learners but prevents admission after offline commits.
    db.scalar(
        select(Card)
        .where(Card.id == card_id)
        .with_for_update(read=True)
        .execution_options(populate_existing=True)
    )
    card, version = published_card(db, card_id, version_id)
    today = business_date(now)
    completion = db.get(Completion, (user.id, card.id))
    first_completion = completion is None
    if completion is None:
        summary = card_summary(db, card.id)
        completion = Completion(
            user_id=user.id,
            card_id=card.id,
            first_completed_at=now,
            last_completed_at=now,
            first_version_id=version.id,
            last_version_id=version.id,
            safe_name=summary["name"],
            thumbnail_id=summary["thumbnail_id"],
        )
        db.add(completion)
    else:
        completion.last_completed_at, completion.last_version_id = now, version.id
    db.flush()
    if db.get(DailyLearning, (user.id, card.id, today)) is None:
        db.add(
            DailyLearning(
                user_id=user.id, card_id=card.id, date=today, accepted_at=now, version_id=version.id
            )
        )
    db.flush()
    first_checkin = db.get(Checkin, (user.id, today)) is None
    if first_checkin:
        db.add(Checkin(user_id=user.id, date=today, accepted_at=now))
    db.flush()
    return {
        "card_id": card.id,
        "version_id": version.id,
        "date": today.isoformat(),
        "first_completion": first_completion,
        "first_checkin_today": first_checkin,
        "state": card_state(db, user.id, card.id, now),
        "statistics": statistics(db, user.id, now),
    }


def learning_records(db, user_id: str, page: int, limit: int):
    query = select(Completion).where(Completion.user_id == user_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(Completion.last_completed_at.desc(), Completion.card_id)
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    return {
        "items": [
            {
                **card_summary(db, row.card_id),
                "first_completed_at": timestamp(row.first_completed_at),
                "last_completed_at": timestamp(row.last_completed_at),
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "limit": limit,
    }


def checkin_records(db, user_id: str, page: int, limit: int):
    query = select(Checkin).where(Checkin.user_id == user_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(Checkin.date.desc()).offset((page - 1) * limit).limit(limit)
    ).all()
    return {
        "items": [
            {
                "date": row.date.isoformat(),
                "card_count": db.scalar(
                    select(func.count())
                    .select_from(DailyLearning)
                    .where(DailyLearning.user_id == user_id, DailyLearning.date == row.date)
                ),
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "limit": limit,
    }


def day_records(db, user_id: str, day: date):
    rows = db.scalars(
        select(DailyLearning)
        .where(DailyLearning.user_id == user_id, DailyLearning.date == day)
        .order_by(DailyLearning.accepted_at.desc(), DailyLearning.card_id)
    ).all()
    return {
        "date": day.isoformat(),
        "total": len(rows),
        "items": [
            {**card_summary(db, row.card_id), "completed_at": timestamp(row.accepted_at)}
            for row in rows
        ],
    }
