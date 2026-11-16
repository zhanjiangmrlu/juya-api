"""Four stable-content counts on the same snapshot as the filtered list."""

from sqlalchemy import case, func, select

from .content_models import Card, CardDraft
from .database import timestamp
from .listening_models import ListeningArticle


def scene_category():
    return case(
        (Card.current_version_id.is_not(None), Card.published_content_type),
        else_=CardDraft.content_type,
    )


def article_category():
    a = ListeningArticle
    return case(
        (a.version_id.is_not(None), a.category_id),
        else_=func.coalesce(a.draft_category_id, a.category_id),
    )


def statistics(db, model, category, now):
    scene = model is Card
    ownership = scene_category() if scene else article_category()
    published = (model.status == "published") & (
        (Card.current_version_id if scene else ListeningArticle.version_id).is_not(None)
    )
    query = (
        select(
            ownership,
            func.count(model.id),
            func.sum(case((published, 1), else_=0)),
            func.sum(case((published & model.is_free, 1), else_=0)),
        )
        .select_from(model)
        .where(model.deleted_at.is_(None))
    )
    if scene:
        query = query.join(CardDraft)
    all_counts = [0, 0, 0]
    selected = [0, 0, 0]
    for value, total, live, free in db.execute(query.group_by(ownership)):
        counts = [int(total), int(live), int(free)]
        all_counts = [a + b for a, b in zip(all_counts, counts, strict=True)]
        if value == category:
            selected = counts

    def view(counts):
        total, live, free = counts
        return {"total": total, "published": live, "free": free, "remaining": live - free}

    return {
        "statistics": view(selected if category else all_counts),
        "all_statistics": view(all_counts),
        "snapshot_at": timestamp(now),
    }
