"""Listening content, one current authorization decision, and transactional learning facts."""

import re
from datetime import timedelta

from sqlalchemy import func, select

from .access_service import authorization, preview_token, read_preview
from .content_models import Media
from .database import timestamp
from .errors import DomainError
from .learning_models import Checkin
from .learning_service import business_date, statistics
from .listening_models import (
    ListeningArticle as Article,
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
    ListeningPolicy as Policy,
)
from .listening_models import (
    ListeningProgress as Progress,
)
from .listening_models import (
    ListeningTopic as Topic,
)
from .listening_models import (
    ListeningVersion as Version,
)
from .listening_timeline import body_tokens, ensure_timeline, timeline_view
from .models import Audit
from .persistence import insert_once
from .security import fingerprint


def catalog_lock(db, *, shared=False):
    insert_once(
        db, Policy, {"id": 1, "free_count": None, "revision": 0, "catalog_revision": 0}, ["id"]
    )
    return db.scalar(
        select(Policy)
        .where(Policy.id == 1)
        .with_for_update(read=shared)
        .execution_options(populate_existing=True)
    )


def changed(db):
    policy = catalog_lock(db)
    policy.catalog_revision += 1
    db.flush()


def require_article(db, article_id, revision=None, *, lock=False, allow_deleted=False):
    query = select(Article).where(Article.id == article_id)
    if lock:
        query = query.with_for_update()
    row = db.scalar(query.execution_options(populate_existing=True))
    if not row:
        raise DomainError(404, "listening_article_missing", "未找到此听读文章")
    if row.deleted_at and not allow_deleted:
        raise DomainError(410, "listening_article_deleted", "文章已删除，不能继续操作")
    if revision is not None and row.revision != revision:
        raise DomainError(409, "listening_article_changed", "文章已变化，请刷新后重新确认")
    return row


def require_topic(db, topic_id):
    row = db.get(Topic, topic_id)
    if not row or not db.get(Category, row.category_id):
        raise DomainError(422, "listening_topic_missing", "请选择已有有效分类和主题")
    return row


def published_rows(db):
    return list(
        db.scalars(
            select(Article)
            .where(
                Article.status == "published",
                Article.deleted_at.is_(None),
                Article.version_id.is_not(None),
            )
            .order_by(Article.global_order, Article.id)
        )
    )


def policy_view(db):
    row = db.get(Policy, 1)
    configured = bool(row and row.free_count is not None)
    ids = [a.id for a in published_rows(db)][: row.free_count] if configured else []
    return {
        "configured": configured,
        "free_count": row.free_count if row else None,
        "revision": row.revision if row else 0,
        "article_ids": ids,
    }


def access(db, user_id, article, now):
    policy = policy_view(db)
    grant = authorization(db, user_id, now)
    available = bool(
        article and article.status == "published" and article.version_id and not article.deleted_at
    )
    free = bool(available and article.id in policy["article_ids"])
    can_learn = bool(available and policy["configured"] and (free or grant["status"] == "active"))
    catalog = db.get(Policy, 1)
    return {
        "can_learn": can_learn,
        "can_lookup": bool(can_learn and grant["status"] == "active"),
        "is_free": free,
        "reason": None
        if can_learn
        else (
            "content_unavailable"
            if not available
            else "learning_authorization_required"
            if policy["configured"]
            else "listening_not_open"
        ),
        "version": (
            f"{policy['revision']}:{catalog.catalog_revision if catalog else 0}:"
            f"{grant['revision']}:{grant['status']}"
        ),
        "server_now": timestamp(now),
        "expires_at": grant["expires_at"],
    }


def published(db, user_id, article_id, now, version_id=None, *, lookup=False, lock=False):
    if lock:
        catalog_lock(db, shared=True)
        now = db.info.get("clock", lambda: now)()
    article = require_article(db, article_id)
    permission = access(db, user_id, article, now)
    if not permission["can_lookup" if lookup else "can_learn"]:
        raise DomainError(
            403,
            "lookup_authorization_required" if lookup else permission["reason"],
            "点词查询需学习授权" if lookup else "此听读文章暂不可学习",
        )
    if version_id and version_id != article.version_id:
        raise DomainError(409, "listening_version_changed", "发布版本已更新，请重新打开文章")
    version = db.get(Version, article.version_id)
    if not version:
        raise DomainError(409, "listening_version_missing", "文章版本不可用，请刷新")
    return article, version


def admin_publication(db, article_id):
    """Resolve the active immutable version without requiring a learner or recording activity."""
    row = require_article(db, article_id)
    version = db.get(Version, row.version_id) if row.version_id else None
    if row.status != "published" or not version or version.article_id != row.id:
        raise DomainError(404, "listening_publication_missing", "当前没有可查看的发布内容")
    return row, version


def published_article_view(db, row, version):
    """Render the publication with the shared Article contract and no draft metadata."""
    return {
        "id": row.id,
        "topic_id": row.topic_id,
        "status": "published",
        "revision": row.revision,
        "version_id": version.id,
        "topic_order": row.topic_order,
        "global_order": row.global_order,
        "payload": version.payload,
        "word_count": len(body_tokens(version.payload["body_en"])),
        "timeline": timeline_view(db, version.payload),
        "created_at": timestamp(row.created_at),
        "deleted_at": None,
        "published_topic_id": row.topic_id,
        "published_topic_order": row.topic_order,
    }


def validate_payload(db, payload, *, resource_owner=None, resource_ids=None):
    tokens = {(m.start(), m.end()): m.group() for m in body_tokens(payload["body_en"])}
    seen = set()
    for meaning in payload.get("word_meanings", []):
        location = (meaning["start"], meaning["end"])
        if tokens.get(location) != meaning["word"] or location in seen:
            raise DomainError(
                422, "listening_word_reference_invalid", "请重新核对本篇词义的正文位置"
            )
        seen.add(location)
    for field, kind in [("audio_id", "audio"), ("image_id", "image")]:
        if payload.get(field):
            medium = db.get(Media, payload[field])
            if (
                not medium
                or medium.kind != kind
                or medium.owner_kind != "listening"
                or (
                    resource_owner is not None
                    and medium.owner_id not in resource_owner
                    and medium.id not in (resource_ids or set())
                )
            ):
                raise DomainError(
                    422, "listening_media_reference_invalid", "素材归属无效，请选择本篇素材"
                )


def publication_errors(db, article):
    payload = article.payload
    errors = []
    require_topic(db, article.topic_id)
    for field in ["title_zh", "title_en", "body_en", "translation_zh"]:
        if not payload.get(field, "").strip():
            errors.append(field + ":required")
    expressions = payload.get("expressions", [])
    if len(expressions) != 5 or any(
        not all(e.get(f, "").strip() for f in ["english", "chinese", "example"])
        for e in expressions
    ):
        errors.append("expressions:five_complete_required")
    audio = db.get(Media, payload["audio_id"]) if payload.get("audio_id") else None
    if not audio or audio.state != "ready" or not audio.playback_id or not audio.duration:
        errors.append("audio_id:ready_playback_required")
    if payload.get("image_id"):
        image = db.get(Media, payload["image_id"])
        if not image or image.state != "ready":
            errors.append("image_id:not_ready")
    return errors


def article_view(db, row):
    version = db.get(Version, row.version_id) if row.version_id else None
    return {
        "id": row.id,
        "topic_id": row.draft_topic_id or row.topic_id,
        "status": row.status,
        "revision": row.revision,
        "version_id": row.version_id,
        "topic_order": row.draft_topic_order
        if row.draft_topic_order is not None
        else row.topic_order,
        "global_order": row.global_order,
        "payload": row.payload,
        "word_count": len(body_tokens(row.payload["body_en"])),
        "timeline": timeline_view(db, row.payload),
        "created_at": timestamp(row.created_at),
        "deleted_at": timestamp(row.deleted_at),
        "has_unpublished_changes": bool(
            row.status != "published"
            or not version
            or version.payload != row.payload
            or row.draft_topic_id
        ),
        "batch_id": row.batch_id,
        "draft_topic_id": row.draft_topic_id,
        "draft_topic_order": row.draft_topic_order,
        "published_topic_id": row.topic_id if row.version_id else None,
        "published_topic_order": row.topic_order if row.version_id else None,
    }


def state(db, user_id, article_id, now):
    return {
        "favorite": db.get(Favorite, (user_id, article_id)) is not None,
        "completed": db.get(Completion, (user_id, article_id)) is not None,
        "today_completed": db.get(Daily, (user_id, article_id, business_date(now))) is not None,
    }


def reading_paragraph(body, progress):
    """Locate saved codepoint progress in nonempty lines without normalizing CR/LF offsets."""
    if not progress or progress["updated_at"] is None:
        return None
    spans = [match for match in re.finditer(r"[^\r\n]+", body) if match.group().strip()]
    for number, span in enumerate(spans, 1):
        if progress["reading_position"] < span.end():
            return number
    return len(spans) or None


def summary(db, row, user_id, now, *, include_progress=False):
    version = db.get(Version, row.version_id) if row.version_id else None
    payload = version.payload if version else row.payload
    available = row.status == "published" and not row.deleted_at and version is not None
    image = db.get(Media, payload["image_id"]) if payload.get("image_id") else None
    audio = db.get(Media, payload["audio_id"]) if available and payload.get("audio_id") else None
    progress = progress_view(db, user_id, row) if include_progress and available else None
    # Thumbnail route resolves only the small derivative, never the protected original.
    thumbnail = (
        f"/api/mini/v1/listening/articles/{row.id}/thumbnail?version_id={version.id}"
        if available and version and image and image.thumbnail_id
        else None
    )
    return {
        "id": row.id,
        "content_type": "listening",
        "topic_id": row.topic_id,
        "title_zh": payload["title_zh"],
        "title_en": payload["title_en"],
        "tags": payload.get("tags", []),
        "word_count": len(body_tokens(payload["body_en"])),
        "version_id": version.id if available and version else None,
        "available": bool(available),
        "thumbnail_url": thumbnail,
        "audio_duration_seconds": audio.duration if audio and audio.state == "ready" else None,
        "progress": progress,
        "reading_paragraph": reading_paragraph(payload["body_en"], progress),
        "access": access(db, user_id, row, now),
        "state": state(db, user_id, row.id, now),
    }


def create_article(db, topic_id, payload, now, *, batch_id=None, source_hash=None, owners=None):
    catalog_lock(db)
    require_topic(db, topic_id)
    validate_payload(db, payload, resource_owner=owners or set())
    row = Article(
        topic_id=topic_id,
        payload=payload,
        batch_id=batch_id,
        source_hash=source_hash,
        topic_order=(
            db.scalar(select(func.max(Article.topic_order)).where(Article.topic_id == topic_id))
            or 0
        )
        + 1,
        created_at=now,
    )
    db.add(row)
    db.flush()
    ensure_timeline(db, payload, now)
    changed(db)
    return row


def imported_media_ids(db, row):
    """Saved immutable candidate facts grant exact imported media, never a whole owner."""
    from .listening_models import ListeningCandidate

    allowed = set()
    for candidate in db.scalars(
        select(ListeningCandidate).where(
            ListeningCandidate.article_id == row.id,
            ListeningCandidate.state == "saved",
            ListeningCandidate.removed.is_(False),
        )
    ):
        applied_ids = (candidate.resources or {}).get("_metadata", {}).get("applied_media_ids")
        for field, kind in [("audio_id", "audio"), ("image_id", "image")]:
            medium_id = candidate.payload.get(field)
            if applied_ids is not None and medium_id not in applied_ids:
                continue
            medium = db.get(Media, medium_id) if medium_id else None
            if (
                medium
                and medium.owner_kind == "listening"
                and medium.owner_id == candidate.batch_id
                and medium.kind == kind
            ):
                allowed.add(medium.id)
    return allowed


def update_article(db, row, body, now, *, imported_ids=None):
    require_topic(db, body.topic_id)
    validate_payload(
        db,
        body.payload.model_dump(),
        resource_owner={row.id, row.batch_id},
        resource_ids=imported_media_ids(db, row) | (imported_ids or set()),
    )
    if (row.draft_topic_id or row.topic_id) != body.topic_id:
        new_order = (
            db.scalar(
                select(func.max(Article.topic_order)).where(Article.topic_id == body.topic_id)
            )
            or 0
        ) + 1
        if row.version_id:
            if body.topic_id == row.topic_id:
                row.draft_topic_id, row.draft_topic_order = None, None
            else:
                row.draft_topic_id, row.draft_topic_order = body.topic_id, new_order
        else:
            row.topic_id, row.topic_order = body.topic_id, new_order
        changed(db)
    row.payload = body.payload.model_dump()
    row.revision += 1
    ensure_timeline(db, row.payload, now)
    db.flush()
    return article_view(db, row)


def preview_article(db, settings, admin_id, row, now):
    token = preview_token(
        settings,
        admin_id,
        "listening.publish",
        {"article_id": row.id, "revision": row.revision, "hash": fingerprint(row.payload)},
        now,
    )
    return {
        "article": article_view(db, row),
        "preview_token": token,
        "errors": publication_errors(db, row),
    }


def publish_article(db, settings, admin_id, row, body, now):
    """Publish an explicit version-checked draft; optional old preview tokens stay validated."""
    if body.preview_token is not None:
        data = read_preview(settings, body.preview_token, admin_id, "listening.publish", now)
        if (
            data["article_id"] != row.id
            or data["revision"] != row.revision
            or data["hash"] != fingerprint(row.payload)
        ):
            raise DomainError(409, "listening_preview_stale", "编辑稿已变化，请重新核对")
    errors = publication_errors(db, row)
    if errors:
        raise DomainError(422, "listening_publish_invalid", "请补齐发布资料", errors)
    current = db.get(Version, row.version_id) if row.version_id else None
    if (
        row.status == "published"
        and current
        and current.payload == row.payload
        and not row.draft_topic_id
    ):
        return article_view(db, row)
    identity = ensure_timeline(db, row.payload, now)
    version = Version(article_id=row.id, payload=row.payload, input_hash=identity, published_at=now)
    db.add(version)
    db.flush()
    if row.draft_topic_id:
        row.topic_id = row.draft_topic_id
        row.topic_order = (
            db.scalar(
                select(func.max(Article.topic_order)).where(
                    Article.topic_id == row.draft_topic_id, Article.id != row.id
                )
            )
            or 0
        ) + 1
        row.draft_topic_id, row.draft_topic_order = None, None
    if row.status != "published":
        row.global_order = (db.scalar(select(func.max(Article.global_order))) or 0) + 1
    row.version_id, row.status = version.id, "published"
    row.revision += 1
    changed(db)
    return article_view(db, row)


def lifecycle(db, row, action, now):
    row.status = "deleted" if action == "delete" else "offline"
    if action == "delete":
        row.deleted_at = now
    row.revision += 1
    changed(db)
    return article_view(db, row)


def progress_view(db, user_id, row):
    progress = db.get(Progress, (user_id, row.id, row.version_id))
    return {
        "version_id": row.version_id,
        "reading_position": progress.reading_position if progress else 0,
        "translation_open": progress.translation_open if progress else False,
        "audio_position": progress.audio_position if progress else 0,
        "playback_rate": progress.playback_rate if progress else 1,
        "updated_at": timestamp(progress.updated_at) if progress else None,
    }


def save_progress(db, user_id, row, version, body, now):
    audio = db.get(Media, version.payload["audio_id"])
    if (
        body.reading_position > len(version.payload["body_en"])
        or body.audio_position > audio.duration + 0.1
    ):
        raise DomainError(422, "listening_progress_invalid", "进度超过正文或音频范围")
    record = db.get(Progress, (user_id, row.id, version.id))
    if not record:
        record = Progress(user_id=user_id, article_id=row.id, version_id=version.id)
        db.add(record)
    for name in ["reading_position", "translation_open", "audio_position", "playback_rate"]:
        setattr(record, name, getattr(body, name))
    record.updated_at = now
    db.flush()
    return progress_view(db, user_id, row)


def complete(db, user, article_id, version_id, now):
    catalog_lock(db, shared=True)
    now = db.info.get("clock", lambda: now)()
    row, version = published(db, user.id, article_id, now, version_id)
    day = business_date(now)
    record = db.get(Completion, (user.id, row.id))
    first = record is None
    if not record:
        record = Completion(
            user_id=user.id,
            article_id=row.id,
            first_completed_at=now,
            last_completed_at=now,
            first_version_id=version.id,
            last_version_id=version.id,
        )
        db.add(record)
    else:
        record.last_completed_at, record.last_version_id = now, version.id
    if not db.get(Daily, (user.id, row.id, day)):
        db.add(
            Daily(
                user_id=user.id, article_id=row.id, date=day, version_id=version.id, accepted_at=now
            )
        )
    first_checkin = db.get(Checkin, (user.id, day)) is None
    if first_checkin:
        db.add(Checkin(user_id=user.id, date=day, accepted_at=now))
    db.flush()
    return {
        "article_id": row.id,
        "version_id": version.id,
        "date": day.isoformat(),
        "first_completion": first,
        "first_checkin_today": first_checkin,
        "state": state(db, user.id, row.id, now),
        "statistics": statistics(db, user.id, now),
    }


def topics(db, user_id, now, category_id=None):
    query = (
        select(Topic)
        .join(Category)
        .order_by(Category.sort_order, Category.id, Topic.sort_order, Topic.id)
    )
    if category_id:
        query = query.where(Topic.category_id == category_id)
    result = []
    valid = published_rows(db)
    completed = set(db.scalars(select(Completion.article_id).where(Completion.user_id == user_id)))
    for row in db.scalars(query):
        ids = {a.id for a in valid if a.topic_id == row.id}
        if ids:
            result.append(
                {
                    "id": row.id,
                    "name": row.name,
                    "name_en": row.name_en or "",
                    "description": row.description,
                    "category_id": row.category_id,
                    "sort_order": row.sort_order,
                    "revision": row.revision,
                    "total_articles": len(ids),
                    "completed_articles": len(ids & completed),
                }
            )
    return result


def next_row(db, user_id, current, now, *, snapshot=None, uncompleted=False):
    rows = list(
        db.scalars(
            select(Article)
            .where(Article.topic_id == current.topic_id, Article.deleted_at.is_(None))
            .order_by(Article.topic_order, Article.id)
        )
    )
    ids = snapshot or [a.id for a in rows]
    if current.id not in ids:
        return None
    index = ids.index(current.id)
    by_id = {a.id: a for a in rows}
    for article_id in ids[index + 1 :]:
        row = by_id.get(article_id)
        if (
            row
            and access(db, user_id, row, now)["can_learn"]
            and (not uncompleted or not db.get(Completion, (user_id, row.id)))
        ):
            return row
    return None


def continue_row(db, user_id, now):
    history = db.scalars(
        select(Progress)
        .where(Progress.user_id == user_id)
        .order_by(Progress.updated_at.desc(), Progress.article_id)
    ).all()
    visited = set()
    for progress in history:
        if progress.article_id in visited:
            continue
        visited.add(progress.article_id)
        row = db.get(Article, progress.article_id)
        if not row or not access(db, user_id, row, now)["can_learn"]:
            continue
        if not db.get(Completion, (user_id, row.id)):
            return row
        following = next_row(db, user_id, row, now, uncompleted=True)
        if following:
            return following
    return None


def order_view(db, scope, topic_id=None):
    if scope == "topic":
        require_topic(db, topic_id)
        query = select(Article).where(Article.topic_id == topic_id, Article.deleted_at.is_(None))
        query = query.order_by(Article.topic_order, Article.id)
    else:
        query = select(Article).where(Article.status == "published", Article.deleted_at.is_(None))
        query = query.order_by(Article.global_order, Article.id)
    policy = db.get(Policy, 1)
    return {
        "revision": policy.catalog_revision if policy else 0,
        "article_ids": [a.id for a in db.scalars(query)],
    }


def save_order(db, body):
    catalog = catalog_lock(db)
    current = order_view(db, body.scope, body.topic_id)
    if body.revision != current["revision"]:
        raise DomainError(409, "listening_order_changed", "排序或发布集合已变化，请刷新确认")
    if len(body.article_ids) != len(set(body.article_ids)) or set(body.article_ids) != set(
        current["article_ids"]
    ):
        raise DomainError(422, "listening_order_incomplete", "请提交完整且无重复的排序集合")
    for index, article_id in enumerate(body.article_ids):
        row = db.get(Article, article_id)
        field = "global_order" if body.scope == "global" else "topic_order"
        if getattr(row, field) != index + 1:
            setattr(row, field, index + 1)
            row.revision += 1
    catalog.catalog_revision += 1
    db.flush()
    return order_view(db, body.scope, body.topic_id)


def free_preview(db, settings, admin_id, count, now):
    current = policy_view(db)
    order = order_view(db, "global")
    ids = order["article_ids"][:count]
    data = {
        "free_count": count,
        "article_ids": ids,
        "revision": current["revision"],
        "catalog_revision": order["revision"],
        "all_ids": order["article_ids"],
    }
    return {
        "preview_token": preview_token(settings, admin_id, "listening.free", data, now),
        "free_count": count,
        "article_ids": ids,
        "revision": current["revision"],
        "added_ids": [a for a in ids if a not in current["article_ids"]],
        "removed_ids": [a for a in current["article_ids"] if a not in ids],
    }


def save_free(db, settings, admin_id, token, now):
    row = catalog_lock(db)
    data = read_preview(settings, token, admin_id, "listening.free", now)
    current = order_view(db, "global")
    if (
        data["catalog_revision"] != current["revision"]
        or data["all_ids"] != current["article_ids"]
        or data["revision"] != row.revision
    ):
        raise DomainError(409, "listening_free_preview_stale", "免费名单已变化，请重新核对确认")
    row.free_count, row.revision = data["free_count"], row.revision + 1
    db.flush()
    return policy_view(db)


def save_free_count(db, count, revision):
    """Save an explicit M directly against the current policy revision and live catalog."""
    row = catalog_lock(db)
    if row.revision != revision:
        raise DomainError(409, "listening_free_changed", "免费设置已变化，请刷新后重新保存")
    row.free_count, row.revision = count, row.revision + 1
    db.flush()
    return policy_view(db)


def audit(db, admin_id, action, now):
    db.add(Audit(admin_id=admin_id, action="listening." + action, occurred_at=now))


def configuration_history(db, admin_id, action, before, after, now):
    """Persist listening configuration facts in the policy/order and receipt transaction."""
    from .access_models import AccessHistory

    db.add(
        AccessHistory(
            admin_id=admin_id,
            action="listening." + action,
            before=before,
            after=after,
            occurred_at=now,
        )
    )


def thumbnail_version(db, article_id, version_id):
    """Allow safe current-publication images without granting full content."""
    row = require_article(db, article_id)
    if row.status != "published" or row.version_id != version_id:
        raise DomainError(404, "listening_thumbnail_missing", "缩略图已更新或不可用")
    version = db.get(Version, version_id)
    if not version:
        raise DomainError(404, "listening_version_missing", "Article version unavailable")
    return version


def queue_token(db, settings, user_id, row, now):
    return preview_token(
        settings,
        user_id,
        "listening.next",
        {
            "article_id": row.id,
            "topic_id": row.topic_id,
            "ids": order_view(db, "topic", row.topic_id)["article_ids"],
        },
        now + timedelta(days=1),
    )
