"""Independent, persisted three-step listening ZIP/DOCX staging and explicit draft saving."""

import hashlib
import re
from pathlib import PurePosixPath
from typing import Literal

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import Field, model_validator
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from . import listening_contracts as C
from . import listening_service as service
from .access_service import preview_token, read_preview
from .content_models import Media
from .database import timestamp
from .dependencies import administrator, database, operation_key, write_transaction
from .errors import DomainError
from .import_parser import W, checked_archive, member_bytes, paragraph_text, xml_document
from .listening_api import mutate_timeline, page_view
from .listening_media import save_media
from .listening_models import (
    ListeningArticle,
    ListeningCandidate,
    ListeningCategory,
    ListeningImport,
    ListeningTopic,
)
from .listening_template import template_document
from .listening_timeline import ensure_timeline, timeline_view
from .models import identifier
from .response_contracts import Page
from .security import fingerprint
from .storage import ObjectStorage
from .transactions import operate
from .zip_names import readable_zip_name


class ImportInput(C.Input):
    mode: Literal["zip", "docx"]


class CandidateInput(C.Revision):
    topic_id: str | None
    payload: C.ListeningPayload
    target_article_id: str | None = Field(default=None, min_length=1, max_length=36)
    target_revision: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def target_pair(self):
        target_fields = {"target_article_id", "target_revision"}
        if self.model_fields_set & target_fields and not target_fields <= self.model_fields_set:
            raise ValueError("目标文章与版本字段必须成对提交")
        if (self.target_article_id is None) != (self.target_revision is None):
            raise ValueError("目标文章与版本必须同时填写或同时清空")
        return self


class Selection(C.Revision):
    candidate_ids: list[str] = Field(min_length=1, max_length=1000)


class ListeningImportSelection(Selection):
    submit_action: Literal["draft", "publish"] = "draft"


class ListeningImportConfirmation(C.Confirmation):
    submit_action: Literal["draft", "publish"] = "draft"


class Resource(C.Input):
    id: str
    name: str
    kind: str
    state: str
    error: str | None = None


class Candidate(C.Input):
    id: str
    package_id: str
    path: str
    state: str
    payload: C.ListeningPayload
    topic_id: str | None
    errors: list[str]
    article_id: str | None
    duplicate_of: str | None
    removed: bool
    timeline: C.Timeline
    resources: dict[str, list[Resource]]
    target_article_id: str | None = None
    target_revision: int | None = None
    submit_action: Literal["draft", "publish"] | None = None
    published_version_id: str | None = None
    parse_error: dict[str, str] | None = None


class Package(C.Input):
    id: str
    name: str
    size: int
    state: str
    error: str | None = None


class Batch(C.Input):
    id: str
    mode: str
    revision: int
    status: str
    packages: list[Package]
    candidates: list[Candidate]
    counts: dict[str, int]
    created_at: str


class ImportPreview(C.Input):
    preview_token: str
    candidate_ids: list[str]
    counts: dict[str, int]
    changes: list["ImportChange"]
    submit_action: Literal["draft", "publish"] = "draft"


class ContentSnapshot(C.Input):
    topic_id: str | None
    payload: C.ListeningPayload


class ImportChange(C.Input):
    candidate_id: str
    operation: Literal["create", "update"]
    target_article_id: str | None
    target_revision: int | None
    before: ContentSnapshot | None
    after: ContentSnapshot


class SaveItem(C.Input):
    candidate_id: str
    status: Literal["success", "failed", "skipped"]
    article_id: str | None = None
    error: str | None = None
    published_version_id: str | None = None


class SaveResult(C.Input):
    batch: Batch
    items: list[SaveItem]
    submit_action: Literal["draft", "publish"] = "draft"


class DocxPreview(C.Input):
    payload: C.ListeningPayload
    hints: dict[str, str]
    topic_id: str | None = None


def owned(db, batch_id, admin_id, revision=None):
    row = db.scalar(
        select(ListeningImport)
        .where(ListeningImport.id == batch_id, ListeningImport.admin_id == admin_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not row:
        raise DomainError(404, "listening_import_missing", "未找到本人可恢复的听读批次")
    if revision is not None and row.revision != revision:
        raise DomainError(409, "listening_import_changed", "本批核对资料已变化，请刷新确认")
    return row


def candidates(db, batch):
    return list(
        db.scalars(
            select(ListeningCandidate)
            .where(ListeningCandidate.batch_id == batch.id)
            .order_by(ListeningCandidate.package_id, ListeningCandidate.path, ListeningCandidate.id)
        )
    )


def target_binding(candidate):
    metadata = (candidate.resources or {}).get("_metadata", {})
    return {
        "target_article_id": metadata.get("target_article_id"),
        "target_revision": metadata.get("target_revision"),
    }


def bound_target(db, candidate, *, lock=False):
    binding = target_binding(candidate)
    if not binding["target_article_id"]:
        return None
    return service.require_article(
        db, binding["target_article_id"], binding["target_revision"], lock=lock
    )


def candidate_media_ids(db, batch, candidate, target=None):
    """Permit this candidate's package resources and its target's actual existing references."""
    allowed = set()
    for kind in ["audio", "image"]:
        for resource in (candidate.resources or {}).get(kind, []):
            medium = db.get(Media, resource.get("id")) if resource.get("id") else None
            if (
                medium
                and medium.owner_kind == "listening"
                and medium.owner_id == batch.id
                and medium.kind == kind
            ):
                allowed.add(medium.id)
    if target:
        previously_imported = service.imported_media_ids(db, target)
        for field, kind in [("audio_id", "audio"), ("image_id", "image")]:
            medium_id = target.payload.get(field)
            medium = db.get(Media, medium_id) if medium_id else None
            if (
                medium
                and medium.kind == kind
                and medium.owner_kind == "listening"
                and (
                    medium.owner_id in {target.id, target.batch_id}
                    or medium.id in previously_imported
                )
            ):
                allowed.add(medium.id)
    return allowed


def validate_candidate_payload(db, batch, candidate, payload, target=None):
    allowed = candidate_media_ids(db, batch, candidate, target)
    service.validate_payload(db, payload, resource_owner=set(), resource_ids=allowed)
    return allowed


def assert_unique_target(db, batch, candidate_id, target_id):
    if target_id and any(
        c.id != candidate_id
        and not c.removed
        and target_binding(c)["target_article_id"] == target_id
        for c in candidates(db, batch)
    ):
        raise DomainError(409, "listening_target_duplicate", "同批不能将多条候选更新到同一文章")


def candidate_fingerprint(candidate):
    return fingerprint(
        {
            "id": candidate.id,
            "topic_id": candidate.topic_id,
            "payload": candidate.payload,
            **target_binding(candidate),
        }
    )


def view(db, batch):
    rows = candidates(db, batch)
    counts = {
        "complete": 0,
        "incomplete": 0,
        "unreadable": 0,
        "duplicate": 0,
        "saved": 0,
        "removed": 0,
        "savable": 0,
        "total": len(rows),
    }
    items = []
    for row in rows:
        if row.removed:
            counts["removed"] += 1
        else:
            counts[row.state] = counts.get(row.state, 0) + 1
            if row.state in {"complete", "incomplete"}:
                counts["savable"] += 1
        items.append(
            {
                "id": row.id,
                "package_id": row.package_id,
                "path": row.path,
                "state": row.state,
                "payload": row.payload,
                "topic_id": row.topic_id,
                "errors": row.errors,
                "article_id": row.article_id,
                "duplicate_of": row.duplicate_of,
                "removed": row.removed,
                "timeline": timeline_view(db, row.payload),
                "resources": {
                    kind: value
                    for kind, value in row.resources.items()
                    if kind in {"audio", "image"}
                },
                **target_binding(row),
                "submit_action": row.resources.get("_metadata", {}).get("submit_action"),
                "published_version_id": row.resources.get("_metadata", {}).get(
                    "published_version_id"
                ),
                "parse_error": row.resources.get("_metadata", {}).get("parse_error"),
            }
        )
    return {
        "id": batch.id,
        "mode": batch.mode,
        "revision": batch.revision,
        "status": batch.status,
        "packages": batch.packages,
        "candidates": items,
        "counts": counts,
        "created_at": timestamp(batch.created_at),
    }


def parse_docx(data):
    """Only explicit field/section labels and expression tables; never infer a title."""
    with checked_archive(data, expanded_limit=30 * 1024 * 1024, file_limit=300) as archive:
        root = xml_document(member_bytes(archive, "word/document.xml", 8 * 1024 * 1024))
    body = root.find(W + "body")
    if body is None:
        raise DomainError(422, "docx_invalid", "文档缺少正文")
    payload = C.ListeningPayload().model_dump()
    section = ""
    paragraphs: dict[str, list[str]] = {"body_en": [], "translation_zh": []}
    sections = {
        "英文正文": "body_en",
        "全文中文译文": "translation_zh",
        "中文译文": "translation_zh",
        "语块": "expressions",
        "5组语块": "expressions",
        "表达": "expressions",
        "5组表达": "expressions",
    }
    hints = {}
    seen_labels = set()
    for element in body:
        if element.tag == W + "p":
            text = paragraph_text(element)
            stripped = text.strip()
            match = re.fullmatch(
                r"(中文标题|英文标题|分类|所属主题|主题|内容标签)\s*[:：]\s*(.*)", stripped
            )
            if match:
                label, value = match.groups()
                label = "主题" if label == "所属主题" else label
                if label in seen_labels:
                    raise DomainError(
                        422,
                        "docx_structure",
                        "一篇资料包含重复字段，请按独立文章拆分",
                        {"stage": "元信息", "field": label},
                    )
                seen_labels.add(label)
                if label in {"中文标题", "英文标题"}:
                    payload["title_zh" if label == "中文标题" else "title_en"] = value
                elif label == "内容标签":
                    payload["tags"] = [x.strip() for x in re.split(r"[,，、]", value) if x.strip()]
                else:
                    hints[label] = value
            elif stripped.rstrip("：:") in sections:
                section = sections[stripped.rstrip("：:")]
            elif section in paragraphs:
                paragraphs[section].append(text)
            elif stripped and section == "expressions":
                # Expressions need three explicit cells, not guessed paragraph pairing.
                raise DomainError(
                    422, "docx_structure", "语块请使用英文、中文释义、替换例句三列表格"
                )
            elif stripped:
                style = element.find("./" + W + "pPr/" + W + "pStyle")
                if (
                    style is not None
                    and style.get(W + "val", "").casefold() == "heading1"
                    and not payload["title_zh"]
                ):
                    payload["title_zh"] = stripped
                else:
                    raise DomainError(
                        422,
                        "docx_structure",
                        "请使用听读模板的明确标题和分区",
                        {"stage": "分区读取", "field": "标题与分区"},
                    )
        elif element.tag == W + "tbl":
            rows = [
                [
                    "\n".join(paragraph_text(p) for p in cell.findall(W + "p")).strip()
                    for cell in row.findall(W + "tc")
                ]
                for row in element.findall(W + "tr")
            ]
            if (
                section != "expressions"
                or not rows
                or rows[0][:3] != ["英文", "中文释义", "替换例句"]
            ):
                raise DomainError(
                    422,
                    "docx_structure",
                    "请核对语块表格的三列字段",
                    {"stage": "语块读取", "field": "英文／中文释义／替换例句"},
                )
            for cells in rows[1:]:
                if len(cells) != 3:
                    raise DomainError(422, "docx_structure", "语块表格不能含合并单元格")
                if any(cells):
                    payload["expressions"].append(
                        dict(zip(["english", "chinese", "example"], cells, strict=True))
                    )
    for field, parts in paragraphs.items():
        while parts and not parts[-1].strip():
            parts.pop()
        payload[field] = "\n".join(parts)
    try:
        return C.ListeningPayload.model_validate(payload).model_dump(), hints
    except ValueError:
        raise DomainError(422, "docx_structure", "资料字段超过限制，请拆分后重试") from None


def matched_topic(db, hints):
    """Resolve explicit Chinese/English names only when one existing owner matches."""

    def normalize(value):
        return (value or "").strip().casefold()

    topic_name, category_name = normalize(hints.get("主题")), normalize(hints.get("分类"))
    if not topic_name:
        return None
    matches = []
    for topic, category in db.execute(
        select(ListeningTopic, ListeningCategory).join(
            ListeningCategory, ListeningTopic.category_id == ListeningCategory.id
        )
    ):
        if topic_name not in {normalize(topic.name), normalize(topic.name_en)}:
            continue
        if category_name and category_name not in {
            normalize(category.name),
            normalize(category.name_en),
        }:
            continue
        matches.append(topic.id)
    return matches[0] if len(matches) == 1 else None


def source_hash(db, payload):
    """Stable semantic document and associated binary content, independent of ZIP names/IDs."""
    normalized = {**payload}
    for name in ["audio_id", "image_id"]:
        medium = db.get(Media, payload.get(name)) if payload.get(name) else None
        normalized[name] = medium.sha256 if medium else None
    return fingerprint(normalized)


def classify(db, candidate):
    """Classify the candidate against live articles and unsaved, active staging only."""
    if candidate.state == "unreadable" or candidate.removed or candidate.article_id:
        return
    candidate.source_hash = source_hash(db, candidate.payload)
    explicit_update = bool(target_binding(candidate)["target_article_id"])
    existing = (
        None
        if explicit_update
        else db.scalar(
            select(ListeningArticle)
            .where(
                ListeningArticle.source_hash == candidate.source_hash,
                ListeningArticle.deleted_at.is_(None),
            )
            .limit(1)
        )
    )
    other = (
        None
        if explicit_update
        else db.scalar(
            select(ListeningCandidate)
            .where(
                ListeningCandidate.source_hash == candidate.source_hash,
                ListeningCandidate.id != candidate.id,
                ListeningCandidate.removed.is_(False),
                ListeningCandidate.article_id.is_(None),
                ListeningCandidate.state.in_(["complete", "incomplete"]),
            )
            .limit(1)
        )
    )
    if existing or other:
        candidate.state = "duplicate"
        if existing:
            candidate.duplicate_of = existing.id
        else:
            assert other is not None
            candidate.duplicate_of = other.article_id or other.id
        candidate.errors = []
        return
    candidate.duplicate_of = None
    errors = []
    for field in ["title_zh", "title_en", "body_en", "translation_zh"]:
        if not candidate.payload[field].strip():
            errors.append(field + ":required_for_publish")
    if not candidate.topic_id:
        errors.append("topic_id:confirmation_required")
    expressions = candidate.payload["expressions"]
    if len(expressions) != 5 or any(
        not all(e[f].strip() for f in ["english", "chinese", "example"]) for e in expressions
    ):
        errors.append("expressions:five_complete_required_for_publish")
    if not candidate.payload.get("audio_id"):
        errors.append("audio_id:selection_required")
    candidate.state, candidate.errors = ("incomplete" if errors else "complete"), errors
    db.flush()


def parse_package(db, settings, batch, name, data, now):
    package_id = identifier()
    checksum = hashlib.sha256(data).hexdigest()
    storage = ObjectStorage(settings)
    storage_key = f"{settings.environment}/imports/{package_id}/{checksum}"
    storage.put(storage_key, data, "application/octet-stream")
    package = {"id": package_id, "name": name, "size": len(data), "state": "ready", "error": None}
    files = []
    if batch.mode == "zip":
        if PurePosixPath(name).suffix.lower() != ".zip":
            raise DomainError(422, "listening_import_mode", "当前批次只接收ZIP资料包")
        with checked_archive(
            data,
            expanded_limit=settings.archive_expanded_limit_mb * 1024 * 1024,
            file_limit=max(1000, settings.import_card_limit * 10),
        ) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                path = readable_zip_name(member.orig_filename, utf8=bool(member.flag_bits & 0x800))
                extension = PurePosixPath(path).suffix.lower()
                if extension in {
                    ".docx",
                    ".mp3",
                    ".m4a",
                    ".wav",
                    ".aac",
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".webp",
                }:
                    limit = (
                        (
                            settings.audio_limit_mb
                            if extension in {".mp3", ".m4a", ".wav", ".aac"}
                            else settings.image_limit_mb
                            if extension != ".docx"
                            else settings.archive_limit_mb
                        )
                        * 1024
                        * 1024
                    )
                    files.append((path, member_bytes(archive, member.filename, limit)))
    else:
        files.append((name, data))
    documents = [(p, d) for p, d in files if PurePosixPath(p).suffix.lower() == ".docx"]
    if len(documents) + len(candidates(db, batch)) > settings.import_card_limit:
        raise DomainError(422, "listening_import_limit", "本批文章超过当前配置上限，请拆分资料")
    if not documents:
        raise DomainError(422, "listening_docx_missing", "未找到可读取的听读DOCX资料")
    for path, document in documents:
        row = ListeningCandidate(
            id=identifier(),
            batch_id=batch.id,
            package_id=package_id,
            path=path,
            state="incomplete",
            payload=C.ListeningPayload().model_dump(),
            resources={},
            errors=[],
        )
        db.add(row)
        db.flush()
        try:
            payload, hints = parse_docx(document)
            row.topic_id = matched_topic(db, hints)
            directory = PurePosixPath(path).parent
            neighbors = [
                (p, d)
                for p, d in files
                if PurePosixPath(p).parent == directory
                and p != path
                and PurePosixPath(p).suffix.lower() != ".docx"
            ]
            resources: dict[str, list[dict]] = {"audio": [], "image": []}
            # An identical sibling candidate can reuse immutable media inputs and timeline.
            for resource_path, raw in neighbors:
                kind = (
                    "audio"
                    if PurePosixPath(resource_path).suffix.lower()
                    in {".mp3", ".m4a", ".wav", ".aac"}
                    else "image"
                )
                sha = hashlib.sha256(raw).hexdigest()
                existing = db.scalar(
                    select(Media)
                    .where(
                        Media.owner_kind == "listening",
                        Media.owner_id == batch.id,
                        Media.kind == kind,
                        Media.sha256 == sha,
                    )
                    .limit(1)
                )
                try:
                    with db.begin_nested():
                        medium = existing or save_media(
                            db, settings, batch.id, kind, raw, resource_path, now
                        )
                    resources[kind].append(
                        {
                            "id": medium.id,
                            "name": resource_path,
                            "kind": kind,
                            "state": medium.state,
                            "error": None,
                        }
                    )
                except DomainError as error:
                    resources[kind].append(
                        {
                            "id": "",
                            "name": resource_path,
                            "kind": kind,
                            "state": "failed",
                            "error": error.code,
                        }
                    )
            for kind in ["audio", "image"]:
                choices = resources[kind]
                if len(choices) == 1 and choices[0]["state"] == "ready":
                    payload[kind + "_id"] = choices[0]["id"]
            row.payload, row.resources = payload, resources
            classify(db, row)
            if row.state != "duplicate":
                ensure_timeline(db, payload, now)
        except DomainError as error:
            row.state, row.errors = "unreadable", [error.code]
            row.resources = {
                **row.resources,
                "_metadata": {
                    "parse_error": {
                        "stage": (error.details or {}).get("stage", "资料读取")
                        if isinstance(error.details, dict)
                        else "资料读取",
                        "field": (error.details or {}).get("field", "内容文档")
                        if isinstance(error.details, dict)
                        else "内容文档",
                        "message": error.message,
                    }
                },
            }
    return package


def selected(db, batch, ids, *, saving=False):
    if len(ids) != len(set(ids)):
        raise DomainError(422, "listening_selection_invalid", "选择不能重复")
    by_id = {c.id: c for c in candidates(db, batch)}
    rows = []
    for candidate_id in ids:
        row = by_id.get(candidate_id)
        if not row or row.removed or (not saving and row.article_id):
            raise DomainError(409, "listening_candidate_changed", "候选已保存或移除，请刷新")
        if saving and (row.state == "unreadable" or not row.topic_id):
            raise DomainError(
                422, "listening_candidate_not_savable", "无法读取或未确认主题的候选不能保存"
            )
        rows.append(row)
    return rows


def routes():
    router = APIRouter(prefix="/api/admin/v1/listening", tags=["listening import staging"])

    @router.get("/template")
    def download_template(admin=Depends(administrator)):
        return Response(
            template_document(),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": 'attachment; filename="listening-template.docx"'},
        )

    @router.post("/docx-preview", response_model=DocxPreview)
    def docx_preview(
        request: Request,
        file: UploadFile = File(...),
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        limit = request.app.state.settings.archive_limit_mb * 1024 * 1024
        raw = file.file.read(limit + 1)
        if not raw or len(raw) > limit:
            raise DomainError(413, "upload_limit", "DOCX为空或超过当前限制")

        def execute():
            payload, hints = parse_docx(raw)
            return {"payload": payload, "hints": hints, "topic_id": matched_topic(db, hints)}

        return operate(
            db,
            admin,
            "admin",
            key,
            "listening.docx.preview",
            {"sha256": hashlib.sha256(raw).hexdigest()},
            request.app.state.clock(),
            execute,
        )

    @router.get("/imports/{batch_id}/media/{media_id}")
    def staged_media(
        batch_id: str,
        media_id: str,
        request: Request,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        batch = owned(db, batch_id, admin.id)
        medium = db.get(Media, media_id)
        allowed = bool(medium and medium.owner_kind == "listening" and medium.owner_id == batch.id)
        if medium and not allowed:
            for candidate in candidates(db, batch):
                if (
                    candidate.removed
                    or candidate.article_id
                    or not target_binding(candidate)["target_article_id"]
                    or media_id
                    not in {candidate.payload.get("audio_id"), candidate.payload.get("image_id")}
                ):
                    continue
                target = bound_target(db, candidate)
                allowed = media_id in candidate_media_ids(db, batch, candidate, target)
                if allowed:
                    break
        if not medium or medium.state != "ready" or not allowed:
            raise DomainError(404, "listening_media_missing", "批次素材暂不可用")
        from .media_api import deliver, playback_medium

        return deliver(playback_medium(db, medium), request)

    @router.get("/imports/{batch_id}/candidates/{candidate_id}/timeline", response_model=C.Timeline)
    def candidate_timeline(
        batch_id: str,
        candidate_id: str,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        batch = owned(db, batch_id, admin.id)
        row = selected(db, batch, [candidate_id])[0]
        validate_candidate_payload(db, batch, row, row.payload, bound_target(db, row))
        return timeline_view(db, row.payload)

    @router.post(
        "/imports/{batch_id}/candidates/{candidate_id}/timeline/{action}", response_model=C.Timeline
    )
    def candidate_timeline_action(
        batch_id: str,
        candidate_id: str,
        action: Literal["retry", "review"],
        body: C.Revision,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        def execute():
            service.catalog_lock(db)
            batch = owned(db, batch_id, admin.id, body.revision)
            row = selected(db, batch, [candidate_id])[0]
            validate_candidate_payload(db, batch, row, row.payload, bound_target(db, row))
            return mutate_timeline(db, admin, row.payload, body, action, request)

        return operate(
            db,
            admin,
            "admin",
            key,
            f"listening.candidate.timeline.{action}:{candidate_id}",
            body.model_dump(),
            request.app.state.clock(),
            execute,
        )

    @router.put("/imports/{batch_id}/candidates/{candidate_id}/timeline", response_model=C.Timeline)
    def candidate_timeline_upload(
        batch_id: str,
        candidate_id: str,
        body: C.TimelineInput,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        def execute():
            service.catalog_lock(db)
            batch = owned(db, batch_id, admin.id, body.revision)
            row = selected(db, batch, [candidate_id])[0]
            validate_candidate_payload(db, batch, row, row.payload, bound_target(db, row))
            return mutate_timeline(db, admin, row.payload, body, "upload", request)

        return operate(
            db,
            admin,
            "admin",
            key,
            f"listening.candidate.timeline.upload:{candidate_id}",
            body.model_dump(),
            request.app.state.clock(),
            execute,
        )

    @router.post("/imports", response_model=Batch)
    def create(
        body: ImportInput,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        def execute():
            batch = ListeningImport(
                admin_id=admin.id, mode=body.mode, packages=[], created_at=request.app.state.clock()
            )
            db.add(batch)
            db.flush()
            return view(db, batch)

        return operate(
            db,
            admin,
            "admin",
            key,
            "listening.import.create",
            body.model_dump(),
            request.app.state.clock(),
            execute,
        )

    @router.get("/imports", response_model=Page[Batch])
    def listing(
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=50),
        unfinished: bool = False,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        query = (
            select(ListeningImport)
            .where(ListeningImport.admin_id == admin.id)
            .order_by(ListeningImport.created_at.desc(), ListeningImport.id)
        )
        if unfinished:
            # Include old batches incorrectly marked saved when actionable candidates remain.
            any_candidate = (
                select(ListeningCandidate.id)
                .where(ListeningCandidate.batch_id == ListeningImport.id)
                .exists()
            )
            actionable = (
                select(ListeningCandidate.id)
                .where(
                    ListeningCandidate.batch_id == ListeningImport.id,
                    ListeningCandidate.removed.is_(False),
                    ListeningCandidate.article_id.is_(None),
                    ListeningCandidate.state.not_in(["saved", "duplicate"]),
                )
                .exists()
            )
            query = query.where(
                or_(
                    actionable,
                    and_(~any_candidate, ListeningImport.status.not_in(["saved", "completed"])),
                )
            )
        return page_view(db, query, page, limit, lambda b: view(db, b))

    @router.get(
        "/imports/{batch_id}", response_model=Batch, dependencies=[Depends(write_transaction)]
    )
    def read(
        batch_id: str,
        request: Request,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        """Recheck this owner's skipped candidates when their duplicate source changes."""
        service.catalog_lock(db)
        batch = owned(db, batch_id, admin.id)
        changed = False
        for row in candidates(db, batch):
            if row.state != "duplicate" or row.removed:
                continue
            before = (row.state, row.duplicate_of)
            classify(db, row)
            if row.state in {"complete", "incomplete"}:
                ensure_timeline(db, row.payload, request.app.state.clock())
            changed = changed or before != (row.state, row.duplicate_of)
        if changed:
            batch.revision += 1
            batch.status = "review"
            db.flush()
        return view(db, batch)

    @router.post("/imports/{batch_id}/files", response_model=Batch)
    def upload(
        batch_id: str,
        revision: int,
        request: Request,
        files: list[UploadFile] = File(...),
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        settings, now = request.app.state.settings, request.app.state.clock()
        if not 1 <= len(files) <= settings.import_card_limit:
            raise DomainError(422, "listening_import_limit", "上传文件数量超过当前限制")
        data = [
            (f.filename or "", f.file.read(settings.archive_limit_mb * 1024 * 1024 + 1))
            for f in files
        ]
        if any(not raw or len(raw) > settings.archive_limit_mb * 1024 * 1024 for _, raw in data):
            raise DomainError(413, "upload_limit", "文件为空或超过当前上传限制")
        if any(
            not name
            or len(name) > 255
            or "/" in name
            or "\\" in name
            or any(ord(c) < 32 for c in name)
            for name, _ in data
        ):
            raise DomainError(422, "upload_filename", "请使用有效文件名")

        def execute():
            service.catalog_lock(db)
            batch = owned(db, batch_id, admin.id, revision)
            packages = list(batch.packages)
            if batch.mode == "docx":
                # One request keeps DOCX and attachments in one isolated package.
                documents = [(n, d) for n, d in data if PurePosixPath(n).suffix.lower() == ".docx"]
                if not documents:
                    raise DomainError(422, "listening_docx_missing", "请上传DOCX及配套素材")
                # Reuse exactly the ZIP directory parser without changing batch mode semantics.
                import io
                import zipfile

                stream = io.BytesIO()
                with zipfile.ZipFile(stream, "w") as archive:
                    for name, raw in data:
                        archive.writestr(name, raw)
                original_mode = batch.mode
                batch.mode = "zip"
                try:
                    packages.append(
                        parse_package(
                            db, settings, batch, documents[0][0] + ".zip", stream.getvalue(), now
                        )
                    )
                finally:
                    batch.mode = original_mode
            else:
                for name, raw in data:
                    try:
                        with db.begin_nested():
                            package = parse_package(db, settings, batch, name, raw, now)
                        packages.append(package)
                    except DomainError as error:
                        package_id = identifier()
                        packages.append(
                            {
                                "id": package_id,
                                "name": name,
                                "size": len(raw),
                                "state": "failed",
                                "error": error.code,
                            }
                        )
                        db.add(
                            ListeningCandidate(
                                batch_id=batch.id,
                                package_id=package_id,
                                path=name,
                                state="unreadable",
                                payload=C.ListeningPayload().model_dump(),
                                errors=[error.code],
                                resources={},
                            )
                        )
            batch.packages, batch.revision, batch.status = packages, batch.revision + 1, "review"
            db.flush()
            return view(db, batch)

        return operate(
            db,
            admin,
            "admin",
            key,
            "listening.import.upload:" + batch_id,
            {
                "revision": revision,
                "files": [
                    {"name": name, "sha256": hashlib.sha256(raw).hexdigest()} for name, raw in data
                ],
            },
            now,
            execute,
        )

    @router.put("/imports/{batch_id}/candidates/{candidate_id}", response_model=Batch)
    def edit(
        batch_id: str,
        candidate_id: str,
        body: CandidateInput,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        def execute():
            service.catalog_lock(db)
            batch = owned(db, batch_id, admin.id, body.revision)
            row = selected(db, batch, [candidate_id])[0]
            if row.state in {"unreadable", "duplicate"}:
                raise DomainError(
                    422, "listening_candidate_readonly", "无法读取或重复候选不可编辑保存"
                )
            if body.topic_id:
                service.require_topic(db, body.topic_id)
            binding = target_binding(row)
            if {"target_article_id", "target_revision"} <= body.model_fields_set:
                binding = {
                    "target_article_id": body.target_article_id,
                    "target_revision": body.target_revision,
                }
            assert_unique_target(db, batch, row.id, binding["target_article_id"])
            target = (
                service.require_article(
                    db, binding["target_article_id"], binding["target_revision"], lock=True
                )
                if binding["target_article_id"]
                else None
            )
            validate_candidate_payload(db, batch, row, body.payload.model_dump(), target)
            row.resources = {**row.resources, "_metadata": binding}
            row.payload, row.topic_id = body.payload.model_dump(), body.topic_id
            classify(db, row)
            ensure_timeline(db, row.payload, request.app.state.clock())
            batch.revision += 1
            batch.status = "review"
            db.flush()
            return view(db, batch)

        return operate(
            db,
            admin,
            "admin",
            key,
            "listening.import.edit:" + candidate_id,
            body.model_dump(exclude_unset=True),
            request.app.state.clock(),
            execute,
        )

    @router.post("/imports/{batch_id}/remove", response_model=Batch)
    def remove(
        batch_id: str,
        body: Selection,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        def execute():
            service.catalog_lock(db)
            batch = owned(db, batch_id, admin.id, body.revision)
            for row in selected(db, batch, body.candidate_ids):
                row.removed = True
            batch.revision, batch.status = batch.revision + 1, "review"
            db.flush()
            return view(db, batch)

        return operate(
            db,
            admin,
            "admin",
            key,
            "listening.import.remove:" + batch_id,
            body.model_dump(),
            request.app.state.clock(),
            execute,
        )

    @router.post("/imports/{batch_id}/preview", response_model=ImportPreview)
    def preview(
        batch_id: str,
        body: ListeningImportSelection,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        def execute():
            service.catalog_lock(db)
            batch = owned(db, batch_id, admin.id, body.revision)
            rows = selected(db, batch, body.candidate_ids, saving=True)
            savable = [r for r in rows if r.state in {"complete", "incomplete"}]
            if not savable:
                raise DomainError(422, "listening_nothing_to_save", "没有可保存的候选")
            changes = []
            snapshots = {}
            for row in savable:
                binding = target_binding(row)
                assert_unique_target(db, batch, row.id, binding["target_article_id"])
                target = bound_target(db, row, lock=True)
                validate_candidate_payload(db, batch, row, row.payload, target)
                changes.append(
                    {
                        "candidate_id": row.id,
                        "operation": "update" if target else "create",
                        **binding,
                        "before": {
                            "topic_id": target.draft_topic_id or target.topic_id,
                            "payload": target.payload,
                        }
                        if target
                        else None,
                        "after": {"topic_id": row.topic_id, "payload": row.payload},
                    }
                )
                snapshots[row.id] = {"fingerprint": candidate_fingerprint(row), **binding}
            token = preview_token(
                request.app.state.settings,
                admin.id,
                "listening.import.save",
                {
                    "batch_id": batch.id,
                    "revision": batch.revision,
                    "candidate_ids": body.candidate_ids,
                    "snapshots": snapshots,
                    "submit_action": body.submit_action,
                },
                request.app.state.clock(),
            )
            return {
                "preview_token": token,
                "candidate_ids": body.candidate_ids,
                "counts": {
                    "selected": len(rows),
                    "savable": len(savable),
                    "skipped": len(rows) - len(savable),
                },
                "changes": changes,
                "submit_action": body.submit_action,
            }

        return operate(
            db,
            admin,
            "admin",
            key,
            "listening.import.preview:" + batch_id,
            body.model_dump(),
            request.app.state.clock(),
            execute,
        )

    @router.post("/imports/{batch_id}/save", response_model=SaveResult)
    def save(
        batch_id: str,
        body: ListeningImportConfirmation,
        request: Request,
        admin=Depends(administrator),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        now = request.app.state.clock()

        def execute():
            service.catalog_lock(db)
            data = read_preview(
                request.app.state.settings,
                body.preview_token,
                admin.id,
                "listening.import.save",
                now,
            )
            if data["batch_id"] != batch_id:
                raise DomainError(409, "listening_import_changed", "核对批次不匹配")
            if data.get("submit_action", "draft") != body.submit_action:
                raise DomainError(
                    409, "listening_import_action_changed", "提交方式已变化，请重新核对"
                )
            batch = owned(db, batch_id, admin.id, data["revision"])
            rows = selected(db, batch, data["candidate_ids"], saving=True)
            results = []
            for row in rows:
                try:
                    with db.begin_nested():
                        if row.article_id or row.state == "saved":
                            receipt = row.resources.get("_metadata", {})
                            if body.submit_action == "publish" and not receipt.get(
                                "published_version_id"
                            ):
                                raise DomainError(
                                    409, "listening_saved_draft", "草稿已保存，请在文章列表明确发布"
                                )
                            results.append(
                                {
                                    "candidate_id": row.id,
                                    "status": "skipped",
                                    "article_id": row.article_id,
                                    "published_version_id": receipt.get("published_version_id"),
                                }
                            )
                            continue
                        if row.state == "duplicate":
                            results.append(
                                {
                                    "candidate_id": row.id,
                                    "status": "skipped",
                                    "article_id": row.duplicate_of,
                                }
                            )
                            continue
                        snapshot = data.get("snapshots", {}).get(row.id)
                        if not snapshot or snapshot.get("fingerprint") != candidate_fingerprint(
                            row
                        ):
                            raise DomainError(
                                409,
                                "listening_import_snapshot_changed",
                                "候选或目标绑定已变化，请重新核对",
                            )
                        binding = target_binding(row)
                        if any(snapshot.get(k) != v for k, v in binding.items()):
                            raise DomainError(
                                409,
                                "listening_import_snapshot_changed",
                                "目标文章或版本已变化，请重新核对",
                            )
                        classify(db, row)
                        if row.state == "duplicate":
                            results.append(
                                {
                                    "candidate_id": row.id,
                                    "status": "skipped",
                                    "article_id": row.duplicate_of,
                                }
                            )
                            continue
                        assert_unique_target(db, batch, row.id, binding["target_article_id"])
                        target = bound_target(db, row, lock=True)
                        imported_ids = validate_candidate_payload(
                            db, batch, row, row.payload, target
                        )
                        same = False
                        if target:
                            same = (
                                source_hash(db, target.payload) == row.source_hash
                                and (target.draft_topic_id or target.topic_id) == row.topic_id
                            )
                            if not same:
                                update = C.ArticleUpdate(
                                    revision=binding["target_revision"],
                                    topic_id=row.topic_id,
                                    payload=row.payload,
                                )
                                service.update_article(
                                    db, target, update, now, imported_ids=imported_ids
                                )
                            article = target
                        else:
                            article = service.create_article(
                                db,
                                row.topic_id,
                                row.payload,
                                now,
                                batch_id=batch.id,
                                source_hash=row.source_hash,
                                owners={batch.id},
                            )
                        published_version_id = None
                        if body.submit_action == "publish":
                            publication = service.publish_article(
                                db,
                                request.app.state.settings,
                                admin.id,
                                article,
                                C.PublishInput(revision=article.revision),
                                now,
                            )
                            published_version_id = publication["version_id"]
                        row.article_id, row.state = article.id, "saved"
                        row.resources = {
                            **row.resources,
                            "_metadata": {
                                **row.resources.get("_metadata", {}),
                                "submit_action": body.submit_action,
                                "published_version_id": published_version_id,
                                "submitted_fingerprint": snapshot["fingerprint"],
                                "applied_media_ids": [
                                    medium_id
                                    for medium_id in [
                                        article.payload.get("audio_id"),
                                        article.payload.get("image_id"),
                                    ]
                                    if medium_id
                                ],
                            },
                        }
                        db.flush()
                    results.append(
                        {
                            "candidate_id": row.id,
                            "status": "skipped"
                            if same and body.submit_action == "draft"
                            else "success",
                            "article_id": row.article_id,
                            "published_version_id": published_version_id,
                        }
                    )
                except DomainError as error:
                    row.resources = {
                        **row.resources,
                        "_metadata": {
                            **row.resources.get("_metadata", {}),
                            "submit_action": body.submit_action,
                        },
                    }
                    results.append(
                        {"candidate_id": row.id, "status": "failed", "error": error.code}
                    )
            batch.status = (
                "partial"
                if any(
                    not candidate.removed
                    and not candidate.article_id
                    and candidate.state not in {"saved", "duplicate"}
                    for candidate in candidates(db, batch)
                )
                else "saved"
            )
            batch.revision += 1
            service.audit(db, admin.id, "import.save", now)
            db.flush()
            return {"batch": view(db, batch), "items": results, "submit_action": body.submit_action}

        return operate(
            db,
            admin,
            "admin",
            key,
            "listening.import.save:" + batch_id,
            body.model_dump(),
            now,
            execute,
        )

    return router
