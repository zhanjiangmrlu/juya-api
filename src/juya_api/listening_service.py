"""Listening content, one current authorization decision, and transactional learning facts."""

import re
from copy import deepcopy
from datetime import timedelta

from sqlalchemy import and_, case, func, select

from . import learning_features
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
from .listening_vocabulary import content_equal, resolve_vocabulary_sources, vocabulary_errors
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


def require_category(db, category_id):
    """Resolve a live category under the caller's common catalog lock."""
    row = db.get(Category, category_id)
    if not row or row.deleted_at:
        raise DomainError(422, "listening_category_missing", "请选择已有有效分类")
    return row


def require_topic(db, topic_id):
    """Map historical topic reads to a live category without allowing topic writes."""
    row = db.get(Topic, topic_id)
    if not row:
        raise DomainError(404, "listening_topic_missing", "旧主题不存在")
    require_category(db, row.category_id)
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
    """Read the full effective explicit free set; legacy count is informational only."""
    row = db.get(Policy, 1)
    ids = list(
        db.scalars(
            select(Article.id)
            .where(
                Article.status == "published",
                Article.deleted_at.is_(None),
                Article.version_id.is_not(None),
                Article.is_free.is_(True),
            )
            .order_by(Article.global_order, Article.id)
        )
    )
    return {
        "configured": True,
        "free_count": len(ids),
        "revision": row.revision if row else 0,
        "article_ids": ids,
    }


def access_snapshot(db, user_id, now):
    """Hold authorization and catalog revision only for this read operation."""
    catalog = db.get(Policy, 1)
    return authorization(db, user_id, now), catalog.catalog_revision if catalog else 0


def access(db, user_id, article, now, *, snapshot=None):
    """Compute publication and free-only permissions while retaining dormant grants."""
    grant, catalog_revision = (
        snapshot if snapshot is not None else access_snapshot(db, user_id, now)
    )
    available = bool(
        article and article.status == "published" and article.version_id and not article.deleted_at
    )
    free = bool(available and article.is_free)
    can_learn = bool(
        available
        and (
            free
            or (learning_features.LEARNING_AUTHORIZATION_ENABLED and grant["status"] == "active")
        )
    )
    return {
        "can_learn": can_learn,
        "can_lookup": bool(
            learning_features.IN_APP_DICTIONARY_ENABLED
            and can_learn
            and grant["status"] == "active"
        ),
        "is_free": free,
        "reason": None
        if can_learn
        else (
            "content_unavailable"
            if not available
            else (
                "learning_authorization_required"
                if learning_features.LEARNING_AUTHORIZATION_ENABLED
                else "content_not_open"
            )
        ),
        "version": (
            f"{article.free_revision if article else 0}:"
            f"{catalog_revision}:"
            f"{grant['revision']}:{grant['status']}:{learning_features.permission_mode()}"
        ),
        "server_now": timestamp(now),
        "expires_at": grant["expires_at"]
        if learning_features.LEARNING_AUTHORIZATION_ENABLED
        else None,
    }


def published(db, user_id, article_id, now, version_id=None, *, lookup=False, lock=False):
    """Fence current content, resources and dictionary access using the same live policy."""
    if lock:
        catalog_lock(db, shared=True)
        now = db.info.get("clock", lambda: now)()
    article = require_article(db, article_id)
    permission = access(db, user_id, article, now)
    if not permission["can_lookup" if lookup else "can_learn"]:
        code = (
            (
                "lookup_authorization_required"
                if learning_features.IN_APP_DICTIONARY_ENABLED
                else "lookup_unavailable"
            )
            if lookup
            else permission["reason"]
        )
        raise DomainError(
            403,
            code,
            "暂未开放"
            if code in {"lookup_unavailable", "content_not_open"}
            else ("点词查询需学习授权" if lookup else "此听读文章暂不可学习"),
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
        "category_id": row.category_id,
        "category_name": category_name(db, row.category_id),
        "category_order": row.category_order,
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
    """纯校验发布必填项及可自动对应的词汇；db 为事务会话，article 为当前草稿"""
    payload = deepcopy(article.payload)
    resolve_vocabulary_sources(payload)
    errors = vocabulary_errors(payload)
    require_category(db, article.draft_category_id or article.category_id)
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
    """Render draft ownership separately from immutable publication metadata."""
    version = db.get(Version, row.version_id) if row.version_id else None
    return {
        "id": row.id,
        "topic_id": row.draft_topic_id or row.topic_id,
        "category_id": row.draft_category_id or row.category_id,
        "category_name": category_name(db, row.draft_category_id or row.category_id),
        "category_order": row.draft_category_order
        if row.draft_category_order is not None
        else row.category_order,
        "draft_category_id": row.draft_category_id,
        "draft_category_order": row.draft_category_order,
        "published_category_id": row.category_id if row.version_id else None,
        "published_category_order": row.category_order if row.version_id else None,
        "is_free": row.is_free,
        "free_revision": row.free_revision,
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
            or not content_equal(version.payload, row.payload)
            or row.draft_category_id
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


def summaries(db, rows, user_id, now, *, include_progress=False, snapshot=None):
    """Fetch all publication dependencies and personal flags once for this batch."""
    if not rows:
        return []
    ids = [row.id for row in rows]
    versions = {
        v.id: v
        for v in db.scalars(
            select(Version).where(
                Version.id.in_([row.version_id for row in rows if row.version_id])
            )
        )
    }
    payloads = [
        versions[row.version_id].payload if row.version_id in versions else row.payload
        for row in rows
    ]
    media_ids = {payload.get(kind) for payload in payloads for kind in ("image_id", "audio_id")}
    media = {m.id: m for m in db.scalars(select(Media).where(Media.id.in_(media_ids - {None})))}
    categories = {
        c.id: c.name
        for c in db.scalars(
            select(Category).where(Category.id.in_({row.category_id for row in rows}))
        )
    }
    flags: dict[str, set[str]] = {}
    for name, model in (
        ("favorite", Favorite),
        ("completed", Completion),
        ("today_completed", Daily),
    ):
        if user_id is None:
            flags[name] = set()
            continue
        query = select(model.article_id).where(model.user_id == user_id, model.article_id.in_(ids))
        if model is Daily:
            query = query.where(Daily.date == business_date(now))
        flags[name] = set(db.scalars(query))
    snapshot = snapshot if snapshot is not None else access_snapshot(db, user_id, now)
    return [
        _summary(
            db,
            row,
            user_id,
            now,
            versions,
            media,
            categories,
            flags,
            snapshot,
            include_progress=include_progress,
        )
        for row in rows
    ]


def summary(db, row, user_id, now, *, include_progress=False, snapshot=None):
    """Render one item using the same batch path as catalog pages."""
    return summaries(db, [row], user_id, now, include_progress=include_progress, snapshot=snapshot)[
        0
    ]


def _summary(
    db, row, user_id, now, versions, media, categories, flags, snapshot, *, include_progress=False
):
    """Render published category labels and optional personal reading progress."""
    version = versions.get(row.version_id)
    payload = version.payload if version else row.payload
    available = row.status == "published" and not row.deleted_at and version is not None
    image = media.get(payload.get("image_id"))
    audio = media.get(payload.get("audio_id")) if available else None
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
        "category_id": row.category_id,
        "category_name": categories.get(row.category_id, ""),
        "category_order": row.category_order,
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
        "access": access(db, user_id, row, now, snapshot=snapshot),
        "state": {name: row.id in values for name, values in flags.items()} if user_id else None,
    }


def category_name(db, category_id):
    """Keep historical summary labels even after safe category soft deletion."""
    owner = db.get(Category, category_id) if category_id else None
    return owner.name if owner else ""


def create_article(db, category_id, payload, now, *, batch_id=None, source_hash=None, owners=None):
    """创建直接归属分类的草稿并补齐词汇来源

    db 为事务会话，category_id 为分类编号，payload 为导入或手填资料，now 为创建时间
    batch_id 为导入批次，source_hash 为原导入身份，owners 为允许复用素材的归属集合
    """
    payload = deepcopy(payload)
    resolve_vocabulary_sources(payload)
    catalog_lock(db)
    require_category(db, category_id)
    validate_payload(db, payload, resource_owner=owners or set())
    row = Article(
        category_id=category_id,
        payload=payload,
        batch_id=batch_id,
        source_hash=source_hash,
        category_order=(
            db.scalar(
                select(func.max(Article.category_order)).where(Article.category_id == category_id)
            )
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
    """更新草稿并保存同一份已匹配来源的资料，发布前保留原发布归属

    db 为事务会话，row 为当前文章，body 为带版本号的修改请求，now 为当前时间
    imported_ids 为本批次允许复用的素材编号
    """
    require_category(db, body.category_id)
    payload = body.payload.model_dump()
    resolve_vocabulary_sources(payload)
    validate_payload(
        db,
        payload,
        resource_owner={row.id, row.batch_id},
        resource_ids=imported_media_ids(db, row) | (imported_ids or set()),
    )
    if (row.draft_category_id or row.category_id) != body.category_id:
        new_order = (
            db.scalar(
                select(func.max(Article.category_order)).where(
                    Article.category_id == body.category_id
                )
            )
            or 0
        ) + 1
        if row.version_id:
            if body.category_id == row.category_id:
                row.draft_category_id, row.draft_category_order = None, None
            else:
                row.draft_category_id, row.draft_category_order = body.category_id, new_order
        else:
            row.category_id, row.category_order = body.category_id, new_order
        changed(db)
    row.payload = payload
    from .listening_imports import source_hash

    row.canonical_hash = source_hash(db, row.payload)
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
    """按已检查版本发布并自动补齐旧草稿的词汇来源

    db 为事务会话，settings 为签发配置，admin_id 为管理员编号，row 为当前文章
    body 为含版本与可选预览令牌的发布请求，now 为发布时间
    """
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
    # 先验证原草稿的预览令牌，再在真正发布事务中保存补齐的位置，读取预览不改草稿
    payload = deepcopy(row.payload)
    resolve_vocabulary_sources(payload)
    if payload != row.payload:
        from .listening_imports import source_hash

        row.payload = payload
        row.canonical_hash = source_hash(db, payload)
    current = db.get(Version, row.version_id) if row.version_id else None
    same_content = current is not None and content_equal(current.payload, row.payload)
    if row.status == "published" and same_content and not row.draft_category_id:
        return article_view(db, row)
    if not same_content:
        identity = ensure_timeline(db, row.payload, now)
        current = Version(
            article_id=row.id, payload=row.payload, input_hash=identity, published_at=now
        )
        db.add(current)
        db.flush()
    if row.draft_category_id:
        # Draft positions are previews; allocate the actual tail under the held catalog lock.
        target = row.draft_category_id
        row.category_order = (
            db.scalar(
                select(func.max(Article.category_order)).where(
                    Article.category_id == target,
                    Article.id != row.id,
                    Article.deleted_at.is_(None),
                )
            )
            or 0
        ) + 1
        row.category_id = target
        row.draft_category_id, row.draft_category_order = None, None
    if row.status != "published":
        row.global_order = (db.scalar(select(func.max(Article.global_order))) or 0) + 1
    assert current is not None
    row.version_id, row.status = current.id, "published"
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
    """Return historical topic-to-category mappings for old navigation links."""
    query = (
        select(Topic)
        .join(Category)
        .where(Category.deleted_at.is_(None))
        .order_by(Category.sort_order, Category.id, Topic.sort_order, Topic.id)
    )
    if category_id:
        query = query.where(Topic.category_id == category_id)
    result = []
    valid = published_rows(db)
    completed = (
        set(db.scalars(select(Completion.article_id).where(Completion.user_id == user_id)))
        if user_id
        else set()
    )
    for row in db.scalars(query):
        ids = {a.id for a in valid if a.category_id == row.category_id}
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
                "completed_articles": len(ids & completed) if user_id else None,
            }
        )
    return result


def category_queue_rows(db, category_id):
    """按学习列表顺序读取分类队列：db 为当前会话，category_id 为文章所属分类"""
    return list(
        db.scalars(
            select(Article)
            .where(Article.category_id == category_id, Article.deleted_at.is_(None))
            .order_by(Article.is_free.desc(), Article.category_order, Article.id)
        )
    )


def next_row(db, user_id, current, now, *, snapshot=None, uncompleted=False):
    """按分类队列选取下一篇并逐篇复核当前权限

    db 为当前数据库会话，user_id 为学习账号，current 为当前文章，now 为服务端时间
    snapshot 为进入时冻结顺序，uncompleted 为是否只选择未完成文章
    """
    rows = category_queue_rows(db, current.category_id)
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


def continue_row(db, user_id, now, *, snapshot=None):
    """Resolve continuation from batched history, category queues and completion facts."""
    history = list(
        db.scalars(
            select(Article)
            .join(Progress, Progress.article_id == Article.id)
            .where(Progress.user_id == user_id)
            .order_by(Progress.updated_at.desc(), Progress.article_id)
        )
    )
    if not history:
        return None
    snapshot = snapshot if snapshot is not None else access_snapshot(db, user_id, now)
    rows = list(
        db.scalars(
            select(Article)
            .where(
                Article.category_id.in_({row.category_id for row in history}),
                Article.deleted_at.is_(None),
            )
            .order_by(Article.is_free.desc(), Article.category_order, Article.id)
        )
    )
    completed = set(
        db.scalars(
            select(Completion.article_id).where(
                Completion.user_id == user_id, Completion.article_id.in_([row.id for row in rows])
            )
        )
    )
    queues: dict[str, list[Article]] = {}
    for row in rows:
        queues.setdefault(row.category_id, []).append(row)
    visited = set()
    for row in history:
        if row.id in visited:
            continue
        visited.add(row.id)
        if not access(db, user_id, row, now, snapshot=snapshot)["can_learn"]:
            continue
        if row.id not in completed:
            return row
        following = False
        for candidate in queues.get(row.category_id, []):
            if candidate.id == row.id:
                following = True
            elif (
                following
                and candidate.id not in completed
                and access(db, user_id, candidate, now, snapshot=snapshot)["can_learn"]
            ):
                return candidate
    return None


def order_view(db, scope, category_id=None):
    """Read only category order; old topic callers receive the corresponding category."""
    if scope == "topic":
        category_id = require_topic(db, category_id).category_id
    if scope in {"category", "topic"}:
        require_category(db, category_id)
        query = (
            select(Article)
            .where(Article.category_id == category_id, Article.deleted_at.is_(None))
            .order_by(Article.category_order, Article.id)
        )
    else:
        query = (
            select(Article)
            .where(Article.status == "published", Article.deleted_at.is_(None))
            .order_by(Article.global_order, Article.id)
        )
    policy = db.get(Policy, 1)
    return {
        "revision": policy.catalog_revision if policy else 0,
        "article_ids": [a.id for a in db.scalars(query)],
    }


def save_order(db, body):
    """Persist revision-checked ordering with an auditable operation receipt."""
    catalog = catalog_lock(db)
    if body.scope != "category":
        raise DomainError(410, "listening_order_retired", "请使用分类内文章排序")
    current = order_view(db, body.scope, body.category_id)
    if body.revision != current["revision"]:
        raise DomainError(409, "listening_order_changed", "排序或发布集合已变化，请刷新确认")
    if len(body.article_ids) != len(set(body.article_ids)) or set(body.article_ids) != set(
        current["article_ids"]
    ):
        raise DomainError(422, "listening_order_incomplete", "请提交完整且无重复的排序集合")
    for index, article_id in enumerate(body.article_ids):
        row = db.get(Article, article_id)
        field = "category_order"
        if getattr(row, field) != index + 1:
            setattr(row, field, index + 1)
            row.revision += 1
    catalog.catalog_revision += 1
    db.flush()
    return order_view(db, body.scope, body.category_id)


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
    """为当前用户和分类封存免费优先队列，后续请求仍逐篇复核实时权限

    db 为当前数据库会话，settings 提供签发密钥，user_id 为学习账号
    row 为当前文章，now 为服务端签发时间
    """
    return preview_token(
        settings,
        user_id,
        "listening.next",
        {
            "article_id": row.id,
            "category_id": row.category_id,
            "ids": [article.id for article in category_queue_rows(db, row.category_id)],
        },
        now + timedelta(days=1),
    )


def categories_progress(db, user_id, now, *, snapshot=None):
    """Aggregate category counts and the first safe thumbnail without per-article reads."""
    grant, _ = snapshot if snapshot is not None else access_snapshot(db, user_id, now)
    live = (
        Article.status == "published",
        Article.deleted_at.is_(None),
        Article.version_id.is_not(None),
    )
    counts_query = (
        select(
            Article.category_id.label("category_id"),
            func.count().label("total"),
            (func.count(Completion.article_id) if user_id else func.count()).label("completed"),
            func.sum(case((Article.is_free.is_(False), 1), else_=0)).label("restricted"),
        )
        .where(*live)
        .group_by(Article.category_id)
    )
    if user_id:
        counts_query = counts_query.outerjoin(
            Completion, and_(Completion.article_id == Article.id, Completion.user_id == user_id)
        )
    counts = counts_query.subquery()
    # Only the first available thumbnail is returned; image JSON stays in the database.
    ranked = (
        select(
            Article.category_id.label("category_id"),
            Article.id.label("article_id"),
            Version.id.label("version_id"),
            func.row_number()
            .over(partition_by=Article.category_id, order_by=(Article.global_order, Article.id))
            .label("rank"),
        )
        .join(Version, Version.id == Article.version_id)
        .join(Media, Media.id == Version.payload["image_id"].as_string())
        .where(*live, Media.thumbnail_id.is_not(None))
        .subquery()
    )
    thumbnails = {
        row.category_id: (
            f"/api/mini/v1/listening/articles/{row.article_id}/thumbnail?version_id={row.version_id}"
        )
        for row in db.execute(select(ranked).where(ranked.c.rank == 1))
    }
    return [
        {
            "id": owner.id,
            "name": owner.name,
            "name_en": owner.name_en,
            "sort_order": owner.sort_order,
            "revision": owner.revision,
            "total_articles": total,
            "completed_articles": completed if user_id else None,
            "restricted_articles": 0
            if (learning_features.LEARNING_AUTHORIZATION_ENABLED and grant["status"] == "active")
            else restricted,
            "thumbnail_url": thumbnails.get(owner.id),
        }
        for owner, total, completed, restricted in db.execute(
            select(Category, counts.c.total, counts.c.completed, counts.c.restricted)
            .join(counts, counts.c.category_id == Category.id)
            .where(Category.deleted_at.is_(None))
            .order_by(Category.sort_order, Category.id)
        )
    ]
