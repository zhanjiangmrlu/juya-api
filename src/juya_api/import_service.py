"""Persistent import staging shares candidate validation and never publishes content."""

import copy
import hashlib
from pathlib import PurePosixPath
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import func, select

from .content_contracts import SceneContent
from .content_models import CardDraft, Media
from .content_service import (
    create_candidate,
    normalize,
    require_card,
    save_candidate,
    validate_publication,
)
from .database import timestamp
from .errors import DomainError
from .import_models import ImportBatch, ImportFile, ImportIdentity, ImportItem
from .import_parser import checked_archive, member_bytes, parse_docx_items
from .job_models import Job
from .jobs import enqueue
from .models import Administrator
from .security import fingerprint
from .storage import ObjectStorage
from .transactions import actor_lock
from .zip_names import import_file_name, readable_zip_name


def owned_batch(db, batch_id, admin_id):
    """Every restore/edit/result query stays inside the signed-in administrator's batch."""
    batch = db.get(ImportBatch, batch_id)
    if not batch or batch.admin_id != admin_id:
        raise DomainError(404, "import_missing", "未找到本次导入")
    return batch


def item_job(db, item):
    return db.get(Job, item.job_id) if item.job_id else None


def content_hash(db, content):
    """Ignore generated IDs, retaining text, confirmed sources and actual immutable media hashes."""
    value = copy.deepcopy(content)
    if not value.get("title_en"):
        value.pop("title_en", None)
    lines = {line["id"]: index for index, line in enumerate(value["dialogue"])}
    for field in ["image_id", "audio_id"]:
        medium = db.get(Media, value[field]) if value[field] else None
        value[field] = medium.sha256 if medium else None
    for group in ["dialogue", "vocabulary", "chunks"]:
        for row in value[group]:
            row.pop("id", None)
            if row.get("source"):
                row["source"]["line_id"] = lines.get(row["source"]["line_id"], -1)
    return fingerprint(value)


def object_key(db, item):
    """Missing media has a stable identity too; filenames never identify a card."""
    image = db.get(Media, item.content["image_id"]) if item.content["image_id"] else None
    audio = db.get(Media, item.content["audio_id"]) if item.content["audio_id"] else None
    return fingerprint(
        {
            "source": item.source_identity,
            "image": image.sha256 if image else None,
            "audio": audio.sha256 if audio else None,
        }
    )


def find_identity(db, item):
    """Retain complete identities and recognize incomplete drafts saved by older releases."""
    identity = db.get(ImportIdentity, object_key(db, item))
    if identity:
        return identity
    previous = db.scalars(
        select(ImportItem).where(
            ImportItem.source_identity == item.source_identity,
            ImportItem.saved_card_id.is_not(None),
        )
    ).all()
    hashed = content_hash(db, item.content)
    for candidate in previous:
        legacy = db.get(ImportIdentity, fingerprint({"incomplete_item": candidate.id}))
        if legacy and (
            legacy.content_hash == hashed or object_key(db, candidate) == object_key(db, item)
        ):
            return legacy
    return None


def source_view(db, item):
    """Derive archive provenance from retained source relationships, including full folder paths."""
    source = db.get(ImportFile, item.source_file_id)
    root = db.get(ImportFile, source.parent_id) if source and source.parent_id else None
    return {
        "source_zip_id": root.id if root else None,
        "source_zip_name": root.name if root else None,
        "source_folder": str(PurePosixPath(import_file_name(db, source)).parent) if root else None,
    }


def validate_source_media(db, batch, item, content):
    """ZIP staging cannot bind attachments from another archive or card folder."""
    if batch.mode != "zip":
        return
    source = db.get(ImportFile, item.source_file_id)
    for field in ["image_id", "audio_id"]:
        if not content[field]:
            continue
        attachment = db.scalar(select(ImportFile).where(ImportFile.media_id == content[field]))
        if attachment and (
            attachment.batch_id != batch.id
            or attachment.parent_id != source.parent_id
            or PurePosixPath(attachment.name).parent != PurePosixPath(source.name).parent
        ):
            raise DomainError(
                422, "import_media_source", "请选择当前ZIP同一卡片文件夹的素材，或单独上传补充资料"
            )


def file_view(db, row):
    """Expose filenames and owned processing status, never filesystem or cloud paths."""
    medium = db.get(Media, row.media_id) if row.media_id else None
    job = (
        db.get(Job, medium.job_id if medium else row.job_id)
        if (medium and medium.job_id) or row.job_id
        else None
    )
    state = (
        "failed"
        if row.error_code or (job and job.state == "failed")
        else medium.state
        if medium
        else "ready"
        if not job or job.state == "succeeded"
        else "processing"
    )
    return {
        "id": row.id,
        "name": import_file_name(db, row),
        "kind": row.kind,
        "size": row.size,
        "media_id": row.media_id,
        "processing_stage": medium.processing_stage if medium else None,
        "state": state,
        "job_id": job.id if job else None,
        "error_code": row.error_code or (job.error_code if job and job.state == "failed" else None),
        "parent_id": row.parent_id,
        "progress": row.progress,
    }


def item_view(db, item):
    job = item_job(db, item)
    image = db.get(Media, item.content["image_id"]) if item.content["image_id"] else None
    hashed = content_hash(db, item.content)
    identity = find_identity(db, item)
    issues = [
        i
        for i in item.parser_issues
        if i["code"] != "title_en_conflict" or not item.content.get("title_en", "").strip()
    ]
    issues += validate_publication(db, item.content)
    if not item.readable:
        state = "unreadable"
    elif job and job.state in {"queued", "running", "retry"}:
        state = "saving"
    elif job and job.state == "failed":
        state = "failed"
    elif (
        job
        and job.result
        and job.result.get("skipped")
        and item.last_saved_hash == hashed
        and not item.target_card_id
    ):
        state = "duplicate"
    elif (
        item.saved_card_id
        and item.last_saved_hash == hashed
        and (not item.target_card_id or item.target_card_id == item.saved_card_id)
    ):
        state = "saved"
    elif identity and identity.content_hash == hashed and not item.target_card_id:
        state = "duplicate"
    else:
        state = "ready" if not issues else "incomplete"
    return {
        "id": item.id,
        "revision": item.revision,
        "content": item.content,
        "thumbnail_id": image.thumbnail_id if image and image.state == "ready" else None,
        "selected": item.selected,
        "readable": item.readable,
        "state": state,
        "issues": issues,
        "source_file_id": item.source_file_id,
        **source_view(db, item),
        "target_card_id": item.target_card_id,
        "target_revision": item.target_revision,
        "saved_card_id": item.saved_card_id,
        "saved_draft_revision": item.saved_draft_revision,
        "suggested_target_id": identity.card_id if identity else None,
        "job_id": item.job_id,
        "error_code": job.error_code if job and job.state == "failed" else None,
    }


def batch_view(db, batch):
    files = db.scalars(
        select(ImportFile)
        .where(ImportFile.batch_id == batch.id)
        .order_by(ImportFile.created_at, ImportFile.id)
    ).all()
    items = db.scalars(
        select(ImportItem)
        .where(ImportItem.batch_id == batch.id)
        .order_by(ImportItem.position, ImportItem.id)
    ).all()
    used = {
        item.content[field]
        for item in items
        for field in ["image_id", "audio_id"]
        if item.content[field]
    }
    return {
        "id": batch.id,
        "mode": batch.mode,
        "created_at": timestamp(batch.created_at),
        "files": [file_view(db, row) for row in files],
        "items": [item_view(db, item) for item in items],
        "unused_file_ids": [
            row.id
            for row in files
            if row.kind == "unused" or (row.kind in {"image", "audio"} and row.media_id not in used)
        ],
    }


def confirmation(db, batch, item_ids=None):
    items = db.scalars(
        select(ImportItem)
        .where(ImportItem.batch_id == batch.id)
        .order_by(ImportItem.position, ImportItem.id)
    ).all()
    if item_ids is not None and (
        not item_ids or len(item_ids) > 50 or not set(item_ids) <= {i.id for i in items}
    ):
        raise DomainError(422, "import_selection_invalid", "重试范围已失效，请重新核对本次卡片")
    files = db.scalars(
        select(ImportFile).where(ImportFile.batch_id == batch.id).order_by(ImportFile.id)
    ).all()
    values = [item_view(db, item) for item in items]
    version = fingerprint(
        {
            "scope": sorted(set(item_ids)) if item_ids is not None else None,
            "files": [(f.id, f.job_id, file_view(db, f)["state"], f.error_code) for f in files],
            "states": [(i["id"], i["state"], i["issues"]) for i in values],
            "items": [
                (
                    i.id,
                    i.revision,
                    i.selected,
                    i.target_card_id,
                    i.target_revision,
                    i.saved_card_id,
                    i.last_saved_hash,
                    i.job_id,
                )
                for i in items
            ],
        }
    )
    selected = [
        i
        for i in values
        if i["selected"]
        and i["readable"]
        and i["state"] not in {"saved", "duplicate", "saving"}
        and (item_ids is None or i["id"] in item_ids)
    ]
    return {
        "version": version,
        "count": len(selected),
        "incomplete": sum(bool(i["issues"]) for i in selected),
        "saved": sum(i["state"] == "saved" for i in values),
        "duplicates": sum(i["state"] == "duplicate" for i in values),
        "excluded": sum(
            not i["selected"] and i["readable"] and i["state"] != "duplicate" for i in values
        ),
        "unreadable": sum(not i["readable"] for i in values),
    }


def resolve(db, batch):
    """Only unique exact names suggest independent DOCX media; never match by upload order."""
    files = db.scalars(
        select(ImportFile).where(
            ImportFile.batch_id == batch.id,
            ImportFile.parent_id == "",
            ImportFile.kind.in_(["image", "audio"]),
        )
    ).all()
    items = db.scalars(select(ImportItem).where(ImportItem.batch_id == batch.id)).all()
    for item in items:
        job = item_job(db, item)
        if not item.readable or (job and job.state in {"queued", "running", "retry"}):
            continue
        content = copy.deepcopy(item.content)
        for kind, field in [("image", "image_id"), ("audio", "audio_id")]:
            if content[field]:
                continue
            candidates = [
                f for f in files if f.kind == kind and PurePosixPath(f.name).stem == content["name"]
            ]
            if len(candidates) == 1 and file_view(db, candidates[0])["state"] == "ready":
                content[field] = candidates[0].media_id
        if content != item.content:
            item.content = content
            item.revision += 1
    db.flush()
    return batch_view(db, batch)


def asset_kind(name):
    """Keep word, chunk and slice attachments out of whole-scene media."""
    path = PurePosixPath(name)
    if any(
        value in path.stem.lower()
        for value in [
            "词汇",
            "单词",
            "语块",
            "切片",
            "word-audio",
            "word_audio",
            "chunk-",
            "slice-",
        ]
    ):
        return "unused"
    extension = path.suffix.lower()
    if extension in {".png", ".jpg", ".jpeg", ".webp"}:
        return "image"
    if extension in {".mp3", ".wav", ".m4a", ".aac"}:
        return "audio"
    if extension == ".docx":
        return "docx"
    return "unused"


def parse_progress(sessions, job, now, phase, processed, total):
    """Persist counters only for the current live lease; stale workers cannot overwrite progress."""
    with sessions.begin() as db:
        current = db.scalar(select(Job).where(Job.id == job["id"]).with_for_update())
        if (
            not current
            or current.state != "running"
            or current.lease != job["lease"]
            or current.lease_expires_at <= now
        ):
            raise DomainError(409, "import_changed", "导入处理已由其他任务接管")
        source = db.get(ImportFile, job["payload"]["file_id"])
        if not source or source.job_id != current.id:
            raise DomainError(409, "import_changed", "导入文件状态已变化")
        source.progress = {"phase": phase, "processed": processed, "total": total}


def prepare_parse(settings, sessions, job, *, clock):
    """Read source data in the Worker, retaining each ZIP folder's independent outcome."""
    with sessions() as db:
        original = db.get(ImportFile, job["payload"]["file_id"])
        if not original or original.job_id != job["id"]:
            raise DomainError(409, "import_changed", "导入文件状态已变化")
        batch = db.get(ImportBatch, original.batch_id)
        source = dict(
            id=original.id,
            batch_id=original.batch_id,
            name=original.name,
            kind=original.kind,
            storage_key=original.storage_key,
            sha256=original.sha256,
            admin_id=batch.admin_id,
            mode=batch.mode,
        )
    storage = ObjectStorage(settings)
    parse_progress(sessions, job, clock(), "reading", 0, 0)
    data = storage.read(source["storage_key"])
    prepared_files = []
    prepared_items = []

    def candidate(file_id, index, content, sha, *, readable=True, issues=None):
        prepared_items.append(
            {
                "id": str(uuid5(NAMESPACE_URL, file_id + ":" + str(index))),
                "source_file_id": file_id,
                "source_index": index,
                "content": content,
                "source_identity": fingerprint({"docx": sha, "section": index}),
                "readable": readable,
                "selected": readable,
                "parser_issues": issues or [],
            }
        )

    if source["kind"] == "docx":
        items = parse_docx_items(data, card_limit=settings.import_card_limit)
        if source["mode"] == "single" and len(items) != 1:
            raise DomainError(422, "single_docx_multiple", "这份DOCX包含多张卡片，请改用批量导入")
        for index, item in enumerate(items):
            if source["mode"] == "single" and not item["readable"]:
                issue = item["issues"][0]
                raise DomainError(422, issue["code"], issue["message"])
            candidate(
                source["id"],
                index,
                item["content"],
                source["sha256"],
                readable=item["readable"],
                issues=item["issues"],
            )
        parse_progress(sessions, job, clock(), "parsing", len(items), len(items))
    else:
        with checked_archive(
            data, expanded_limit=settings.archive_expanded_limit_mb * 1024 * 1024
        ) as archive:
            members = sorted(
                (
                    i
                    for i in archive.infolist()
                    if not i.is_dir()
                    and "__MACOSX" not in PurePosixPath(i.filename).parts
                    and not any(part.startswith("._") for part in PurePosixPath(i.filename).parts)
                    and PurePosixPath(i.filename).name != ".DS_Store"
                ),
                key=lambda i: i.filename,
            )
            folders = {
                str(PurePosixPath(i.filename).parent)
                for i in members
                if PurePosixPath(i.filename).suffix.lower() == ".docx"
            }
            if len(folders) > settings.import_card_limit:
                raise DomainError(
                    422, "import_card_limit", "压缩包卡片数量超过当前限制，请拆分资料"
                )
            by_folder: dict[str, list[dict[str, Any]]] = {}
            parse_progress(sessions, job, clock(), "reading", 0, len(folders))
            for member in members:
                # Keep the raw lookup/UUID key so old queued jobs retain their identity.
                name = readable_zip_name(member.filename, utf8=bool(member.flag_bits & 0x800))
                kind = asset_kind(member.filename)
                if kind == "unused":
                    prepared_files.append(
                        {
                            "id": str(uuid5(NAMESPACE_URL, source["id"] + ":" + member.filename)),
                            "name": name,
                            "kind": "unused",
                            "storage_key": "",
                            "size": member.file_size,
                            "sha256": "",
                            "media_id": None,
                        }
                    )
                    continue
                limit = (
                    (
                        settings.image_limit_mb
                        if kind == "image"
                        else settings.audio_limit_mb
                        if kind == "audio"
                        else settings.archive_limit_mb
                    )
                    * 1024
                    * 1024
                )
                file_id = str(uuid5(NAMESPACE_URL, source["id"] + ":" + member.filename))
                try:
                    body = member_bytes(archive, member.filename, limit)
                except DomainError as error:
                    entry = {
                        "id": file_id,
                        "name": name,
                        "kind": kind,
                        "storage_key": "",
                        "size": member.file_size,
                        "sha256": "",
                        "media_id": None,
                        "error_code": "archive_member_limit"
                        if error.code == "archive_limit"
                        else "archive_member_invalid",
                    }
                    prepared_files.append(entry)
                    by_folder.setdefault(str(PurePosixPath(member.filename).parent), []).append(
                        entry
                    )
                    continue
                sha = hashlib.sha256(body).hexdigest()
                key = f"{settings.environment}/imports/{file_id}/{sha}"
                storage.put(key, body, "application/octet-stream")
                entry = {
                    "id": file_id,
                    "name": name,
                    "kind": kind,
                    "storage_key": key,
                    "size": len(body),
                    "sha256": sha,
                    "media_id": str(uuid5(NAMESPACE_URL, file_id + ":media"))
                    if kind in {"image", "audio"}
                    else None,
                }
                prepared_files.append(entry)
                by_folder.setdefault(str(PurePosixPath(member.filename).parent), []).append(entry)
            for folder_index, folder in enumerate(sorted(folders)):
                files = by_folder.get(folder, [])
                documents = [f for f in files if f["kind"] == "docx"]
                document = documents[0]
                try:
                    if folder == "." or len(documents) != 1:
                        raise DomainError(
                            422,
                            "zip_folder_docx_count",
                            "一张卡片一个文件夹，每个文件夹只放一份内容DOCX",
                        )
                    if document.get("error_code"):
                        raise DomainError(
                            422,
                            document["error_code"],
                            "此文件夹内容DOCX无法读取或超过限制，请修正文件",
                        )
                    parsed_items = parse_docx_items(
                        storage.read(document["storage_key"]), card_limit=settings.import_card_limit
                    )
                    contents = [i["content"] for i in parsed_items]
                    if len(contents) != 1:
                        raise DomainError(
                            422,
                            "zip_folder_multiple_cards",
                            "一个文件夹应只有一张卡片，请拆分文件夹，或改用上传DOCX及配套资料",
                        )
                    content = contents[0]
                    for kind, field in [("image", "image_id"), ("audio", "audio_id")]:
                        values = [f for f in files if f["kind"] == kind]
                        if len(values) == 1:
                            content[field] = values[0]["media_id"]
                    candidate(
                        document["id"],
                        0,
                        content,
                        document["sha256"],
                        readable=parsed_items[0]["readable"],
                        issues=parsed_items[0]["issues"],
                    )
                except DomainError as error:
                    content = normalize(
                        SceneContent(name=PurePosixPath(document["name"]).parent.name)
                    )
                    candidate(
                        document["id"],
                        0,
                        content,
                        document["sha256"],
                        readable=False,
                        issues=[{"field": "source", "code": error.code, "message": error.message}],
                    )
                parse_progress(sessions, job, clock(), "parsing", folder_index + 1, len(folders))
    if not prepared_items:
        raise DomainError(422, "import_empty", "没有读取到可恢复卡片，请检查文件夹结构或一级标题")

    def apply(db, row):
        actor_lock(db, db.get(Administrator, source["admin_id"]), "admin")
        current = db.get(ImportFile, source["id"])
        if not current or current.job_id != row.id:
            raise DomainError(409, "import_changed", "导入文件状态已变化")
        existing = (
            db.scalar(
                select(func.count())
                .select_from(ImportItem)
                .where(ImportItem.batch_id == source["batch_id"])
            )
            or 0
        )
        new_items = [value for value in prepared_items if not db.get(ImportItem, value["id"])]
        if existing + len(new_items) > settings.import_card_limit:
            raise DomainError(422, "import_card_limit", "本批卡片总数超过当前限制，请开始新的导入")
        for value in prepared_files:
            existing_file = db.get(ImportFile, value["id"])
            if existing_file:
                # Retried old parses keep IDs and payloads while normalizing their labels.
                existing_file.name = value["name"]
                continue
            values = dict(value)
            media_id = values.pop("media_id")
            if media_id:
                medium = Media(
                    id=media_id,
                    owner_kind="admin",
                    owner_id=source["admin_id"],
                    kind=values["kind"],
                    state="processing",
                    storage_key=values["storage_key"],
                    content_type="application/octet-stream",
                    size=values["size"],
                    sha256=values["sha256"],
                    created_at=row.updated_at,
                )
                db.add(medium)
                medium.job_id = enqueue(
                    db,
                    "media.decode",
                    "admin",
                    source["admin_id"],
                    {"media_id": media_id},
                    row.updated_at,
                    settings=settings,
                ).id
                db.flush()
            db.add(
                ImportFile(
                    **values,
                    batch_id=source["batch_id"],
                    parent_id=source["id"],
                    media_id=media_id,
                    created_at=row.updated_at,
                )
            )
        db.flush()
        for index, value in enumerate(new_items):
            if not db.get(ImportItem, value["id"]):
                db.add(
                    ImportItem(
                        **value, batch_id=source["batch_id"], revision=1, position=existing + index
                    )
                )
        current.progress = {
            "phase": "parsed",
            "processed": len(prepared_items),
            "total": len(prepared_items),
        }

    return {
        "file_id": source["id"],
        "items": len(prepared_items),
        "filename_encoding": "unicode",
    }, apply


def prepare_save(settings, sessions, job, now):
    """Each reviewed item saves atomically and remembers its stable card mapping on retries."""
    payload = job["payload"]
    result: dict[str, Any] = {}

    def apply(db, row):
        actor_lock(db, db.get(Administrator, job["owner_id"]), "admin")
        item = db.get(ImportItem, payload["item_id"])
        if not item or item.job_id != row.id or item.revision != payload["revision"]:
            raise DomainError(409, "import_changed", "核对资料已变化，请重新确认保存范围")
        content = SceneContent.model_validate(payload["content"])
        hashed = content_hash(db, payload["content"])
        identity_key = object_key(db, item)
        identity = find_identity(db, item)
        target = payload.get("target_card_id") or item.saved_card_id
        target_revision = (
            payload.get("target_revision")
            if payload.get("target_card_id")
            else item.saved_draft_revision
        )
        if identity and identity.content_hash == hashed and not target:
            card = require_card(db, identity.card_id)
            result["skipped"] = True
        elif identity and not target:
            raise DomainError(
                409, "import_target_required", "资料已存在且本次内容有变化，请明确核对更新目标"
            )
        elif target:
            card = save_candidate(db, target, target_revision, content, job["owner_id"], now)
        else:
            card = create_candidate(db, content, job["owner_id"], now)
        draft = db.get(CardDraft, card.id)
        item.saved_card_id = card.id
        item.saved_draft_revision = draft.revision
        item.last_saved_hash = hashed
        db.merge(
            ImportIdentity(
                object_key=identity_key,
                card_id=card.id,
                content_hash=hashed,
                draft_revision=draft.revision,
            )
        )
        result["card_id"] = card.id

    return result, apply
