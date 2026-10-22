"""Same-page upload/review/save workflow backed by persistent batches and item receipts."""

import hashlib
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, true
from sqlalchemy.orm import Session

from .content_contracts import SceneContent
from .content_models import CardDraft, Media
from .content_service import normalize, require_card, revision_matches
from .dependencies import administrator, database, operation_key
from .errors import DomainError
from .import_models import ImportBatch, ImportFile, ImportItem
from .import_service import (
    INVALID_SOURCE_ERRORS,
    batch_view,
    confirmation,
    file_view,
    item_job,
    item_view,
    owned_batch,
    resolve,
    touch_batch,
    validate_source_media,
)
from .job_models import Job
from .jobs import enqueue
from .media_api import save_media
from .models import Audit, identifier
from .response_contracts import FieldIssue
from .storage import ObjectStorage
from .transactions import operate


class CreateImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["zip", "docx"]
    single_card: bool = False


class ImportProgress(BaseModel):
    phase: Literal["reading", "parsing", "parsed"]
    processed: int
    total: int


class ImportFileView(BaseModel):
    processing_stage: str | None = None
    id: str
    name: str
    kind: str
    size: int
    media_id: str | None
    state: str
    job_id: str | None
    error_code: str | None
    parent_id: str
    progress: ImportProgress | None = None


class ImportItemView(BaseModel):
    id: str
    revision: int
    content: SceneContent
    thumbnail_id: str | None
    selected: bool
    readable: bool
    state: str
    issues: list[FieldIssue]
    source_file_id: str
    source_zip_id: str | None = None
    source_zip_name: str | None = None
    source_folder: str | None = None
    target_card_id: str | None
    target_revision: int | None
    saved_card_id: str | None
    saved_draft_revision: int | None
    suggested_target_id: str | None
    job_id: str | None
    error_code: str | None


class ImportBatchView(BaseModel):
    id: str
    mode: str
    created_at: str
    updated_at: str
    resumable: bool
    stage: Literal["upload", "processing", "review", "result"]
    source_names: list[str]
    files: list[ImportFileView]
    items: list[ImportItemView]
    unused_file_ids: list[str]


class ImportConfirmation(BaseModel):
    version: str
    count: int
    incomplete: int
    saved: int
    duplicates: int
    excluded: int
    unreadable: int


class StageItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    content: SceneContent
    selected: bool
    target_card_id: str | None = Field(default=None, max_length=36)
    target_revision: int | None = Field(default=None, ge=1)
    update_confirmed: bool = False


class AcceptSave(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str = Field(min_length=64, max_length=64)
    confirmed: Literal[True]
    item_ids: list[str] | None = Field(default=None, min_length=1, max_length=50)


class RemoveImportFiles(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Failed ZIP roots do not count toward the card limit; the whole selection is atomic
    file_ids: list[Annotated[str, Field(min_length=1, max_length=36)]] = Field(min_length=1)


class RemoveImportItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=36)
    revision: int = Field(ge=1)


class RemoveImportItems(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[RemoveImportItem] = Field(min_length=1, max_length=50)


def require_removable(items):
    """Accepted save tasks and their durable card results cannot be discarded."""
    if any(item.job_id or item.saved_card_id for item in items):
        raise DomainError(
            409, "import_removal_saved", "资料已提交保存，请保留导入结果并在卡片管理中处理"
        )


def routes():
    router = APIRouter(prefix="/api/admin/v1", tags=["recoverable content import"])

    @router.post("/imports", status_code=201, response_model=ImportBatchView)
    def create(
        body: CreateImport,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        now = request.app.state.clock()

        def execute():
            if body.single_card and body.mode != "docx":
                raise DomainError(422, "import_mode", "单卡导入请选择DOCX")
            accepted = request.app.state.clock()
            batch = ImportBatch(
                admin_id=admin.id,
                mode="single" if body.single_card else body.mode,
                created_at=accepted,
                updated_at=accepted,
            )
            db.add(batch)
            db.flush()
            return batch_view(db, batch, request.app.state.settings)

        return operate(db, admin, "admin", key, "import.create", body.model_dump(), now, execute)

    @router.get("/imports", response_model=list[ImportBatchView])
    def recent(
        request: Request,
        resumable_only: bool = False,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        """Recovery is the complete owned set; the default recent-history query stays compatible."""
        query = (
            select(ImportBatch)
            .where(ImportBatch.admin_id == admin.id, ImportBatch.mode != "single")
            .order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc())
        )
        rows = db.scalars(query if resumable_only else query.limit(5)).all()
        values = [batch_view(db, batch, request.app.state.settings) for batch in rows]
        if resumable_only:
            return sorted(
                [value for value in values if value["resumable"]],
                key=lambda value: (value["updated_at"], value["id"]),
                reverse=True,
            )
        return values

    @router.get("/imports/example", response_class=FileResponse)
    def example(admin=Depends(administrator)):
        return FileResponse(
            Path(__file__).parent / "assets" / "import-example.zip",
            media_type="application/zip",
            filename="句芽英语-资料填写示例.zip",
        )

    @router.get("/imports/{batch_id}", response_model=ImportBatchView)
    def read(
        batch_id: str,
        request: Request,
        require_resumable: bool = False,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        if require_resumable:
            batch = db.get(ImportBatch, batch_id)
            if not batch or batch.admin_id != admin.id:
                raise DomainError(
                    409, "import_not_resumable", "该批次已失效或无权访问，请刷新待处理批次"
                )
            value = batch_view(db, batch, request.app.state.settings)
            if not value["resumable"]:
                raise DomainError(
                    409,
                    "import_not_resumable",
                    "该批次已处理完成或暂存资料不可恢复，请刷新列表；缺失原文件请重新选择上传",
                )
            return value
        return batch_view(db, owned_batch(db, batch_id, admin.id), request.app.state.settings)

    @router.post("/imports/{batch_id}/files", status_code=201, response_model=ImportFileView)
    def upload(
        batch_id: str,
        request: Request,
        kind: Literal["zip", "docx", "image", "audio"],
        file: UploadFile = File(...),
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        batch = owned_batch(db, batch_id, admin.id)
        if (
            (batch.mode == "zip" and kind != "zip")
            or (batch.mode == "docx" and kind == "zip")
            or (batch.mode == "single" and kind != "docx")
        ):
            raise DomainError(422, "import_mode", "一批只能选择一种资料上传方式")
        settings, now = request.app.state.settings, request.app.state.clock()
        name = PurePosixPath((file.filename or "").replace("\\", "/")).name
        if not name or len(name) > 255 or not name.isprintable():
            raise DomainError(422, "import_filename", "文件名不可用，请重命名后上传")
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
        data = file.file.read(limit + 1)
        if not data or len(data) > limit:
            raise DomainError(413, "upload_limit", "文件为空或超过当前上传限制")
        sha = hashlib.sha256(data).hexdigest()

        def execute():
            # Preflight loaded this batch before the actor lock; retain newer accepted edits.
            db.refresh(batch, attribute_names=["updated_at"])
            previous = db.scalar(
                select(ImportFile).where(
                    ImportFile.batch_id == batch_id,
                    ImportFile.parent_id == "",
                    true() if kind == "zip" else ImportFile.name == name,
                    ImportFile.kind == kind if kind == "zip" else true(),
                    ImportFile.sha256 == sha,
                )
            )
            if previous:
                if previous.kind != kind:
                    raise DomainError(
                        409, "import_file_kind", "同一文件已按其他方式接收，请核对文件类型"
                    )
                return file_view(db, previous)
            file_id = identifier()
            row = ImportFile(
                id=file_id,
                batch_id=batch_id,
                parent_id="",
                name=name,
                kind=kind,
                size=len(data),
                sha256=sha,
                storage_key="",
                created_at=now,
            )
            if kind in {"image", "audio"}:
                medium = save_media(
                    db, settings, admin, "admin", kind, data, now, original_name=name
                )
                row.media_id = medium.id
                row.storage_key = medium.storage_key
                row.job_id = medium.job_id
            else:
                storage_key = f"{settings.environment}/imports/{file_id}/{sha}"
                ObjectStorage(settings).put(storage_key, data, "application/octet-stream")
                row.storage_key = storage_key
                row.job_id = enqueue(
                    db,
                    "import.parse",
                    "admin",
                    admin.id,
                    {"file_id": file_id},
                    now,
                    settings=settings,
                ).id
            db.add(row)
            touch_batch(batch, request.app.state.clock, db=db)
            db.flush()
            return file_view(db, row)

        return operate(
            db,
            admin,
            "admin",
            key,
            "import.file:" + batch_id,
            {"name": name, "kind": kind, "sha256": sha},
            now,
            execute,
        )

    @router.post("/imports/{batch_id}/files/remove", response_model=ImportBatchView)
    def remove_files(
        batch_id: str,
        body: RemoveImportFiles,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        """Discard selected ZIP staging atomically; immutable media and receipts remain."""
        now = request.app.state.clock()

        def execute():
            batch = owned_batch(db, batch_id, admin.id)
            ids = set(body.file_ids)
            roots = db.scalars(select(ImportFile).where(ImportFile.id.in_(ids))).all()
            if len(roots) != len(ids) or any(
                row.batch_id != batch_id or row.parent_id or row.kind != "zip" for row in roots
            ):
                raise DomainError(404, "import_file_missing", "未找到本次导入ZIP，请刷新后重新选择")
            files = db.scalars(
                select(ImportFile).where(
                    ImportFile.batch_id == batch_id,
                    (ImportFile.id.in_(ids)) | (ImportFile.parent_id.in_(ids)),
                )
            ).all()
            items = db.scalars(
                select(ImportItem).where(
                    ImportItem.batch_id == batch_id,
                    ImportItem.source_file_id.in_([row.id for row in files]),
                )
            ).all()
            require_removable(items)
            removed_job_ids = {
                value
                for value in (
                    *[row.job_id for row in files],
                    *[file_view(db, row)["job_id"] for row in files],
                    *[item.job_id for item in items],
                )
                if value
            }
            touch_batch(batch, request.app.state.clock, db=db, job_ids=removed_job_ids)
            for item in items:
                db.delete(item)
            db.flush()
            for row in files:
                db.delete(row)
            db.add(
                Audit(
                    admin_id=admin.id,
                    action="import.remove_files",
                    object_id=batch_id,
                    occurred_at=now,
                )
            )
            db.flush()
            # A parse-progress writer may have held the file lock until this
            # deletion. Read its final committed time using the retained IDs.
            touch_batch(batch, request.app.state.clock, db=db, job_ids=removed_job_ids)
            return batch_view(db, batch, request.app.state.settings)

        return operate(
            db,
            admin,
            "admin",
            key,
            "import.files.remove:" + batch_id,
            body.model_dump(),
            now,
            execute,
        )

    @router.post("/imports/{batch_id}/items/remove", response_model=ImportBatchView)
    def remove_items(
        batch_id: str,
        body: RemoveImportItems,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        """Remove only reviewed item revisions, retaining siblings and source archives."""
        now = request.app.state.clock()

        def execute():
            batch = owned_batch(db, batch_id, admin.id)
            requested = {value.id: value.revision for value in body.items}
            if len(requested) != len(body.items):
                raise DomainError(422, "import_selection_invalid", "请勿重复选择同一张卡片")
            items = db.scalars(
                select(ImportItem).where(
                    ImportItem.batch_id == batch_id,
                    ImportItem.id.in_(requested),
                )
            ).all()
            if len(items) != len(requested):
                raise DomainError(
                    404, "import_item_missing", "未找到本次核对资料，请刷新后重新选择"
                )
            require_removable(items)
            if any(item.revision != requested[item.id] for item in items):
                raise DomainError(409, "import_changed", "核对资料已变化，请刷新后重新选择移除范围")
            touch_batch(batch, request.app.state.clock, db=db)
            for item in items:
                db.delete(item)
            db.add(
                Audit(
                    admin_id=admin.id,
                    action="import.remove_items",
                    object_id=batch_id,
                    occurred_at=now,
                )
            )
            db.flush()
            return batch_view(db, batch, request.app.state.settings)

        return operate(
            db,
            admin,
            "admin",
            key,
            "import.items.remove:" + batch_id,
            body.model_dump(),
            now,
            execute,
        )

    @router.post("/imports/{batch_id}/files/{file_id}/retry", response_model=ImportFileView)
    def retry_file(
        batch_id: str,
        file_id: str,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        now, settings = request.app.state.clock(), request.app.state.settings

        def execute():
            batch = owned_batch(db, batch_id, admin.id)
            row = db.get(ImportFile, file_id)
            if not row or row.batch_id != batch_id:
                raise DomainError(404, "import_file_missing", "未找到本次导入文件")
            if row.error_code:
                raise DomainError(
                    422, "import_file_invalid", "包内文件无法读取，请修正后重新上传资料包"
                )
            medium = db.get(Media, row.media_id) if row.media_id else None
            previous = db.get(Job, medium.job_id if medium else row.job_id)
            if not previous or previous.state != "failed":
                return file_view(db, row)
            if previous.error_code in INVALID_SOURCE_ERRORS:
                raise DomainError(
                    422, "import_file_invalid", "原文件无法读取，请按提示修正后重新上传"
                )
            if not ObjectStorage(settings).exists(row.storage_key):
                raise DomainError(409, "import_not_resumable", "原文件已不可用，请重新选择文件上传")
            job = enqueue(
                db,
                "media.decode" if medium else "import.parse",
                "admin",
                admin.id,
                {"media_id": medium.id} if medium else {"file_id": row.id},
                now,
                settings=settings,
            )
            row.job_id = job.id
            if medium:
                medium.job_id, medium.state = job.id, "processing"
            touch_batch(batch, request.app.state.clock, db=db, job_ids=[previous.id])
            db.flush()
            return file_view(db, row)

        return operate(db, admin, "admin", key, "import.file.retry:" + file_id, {}, now, execute)

    @router.post("/imports/{batch_id}/resolve", response_model=ImportBatchView)
    def match(
        batch_id: str,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        return operate(
            db,
            admin,
            "admin",
            key,
            "import.resolve:" + batch_id,
            {},
            request.app.state.clock(),
            lambda: resolve(
                db,
                owned_batch(db, batch_id, admin.id),
                request.app.state.settings,
                request.app.state.clock,
            ),
        )

    @router.patch("/imports/{batch_id}/items/{item_id}", response_model=ImportItemView)
    def stage(
        batch_id: str,
        item_id: str,
        body: StageItem,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        now = request.app.state.clock()

        def execute():
            batch = owned_batch(db, batch_id, admin.id)
            item = db.get(ImportItem, item_id)
            if not item or item.batch_id != batch_id or not item.readable:
                raise DomainError(404, "import_item_missing", "此资料无法核对，请更换文件")
            if item.revision != body.revision:
                raise DomainError(
                    409, "import_changed", "另一窗口已修改核对资料，请获取最新版本后核对"
                )
            job = item_job(db, item)
            if job and job.state in {"queued", "running", "retry"}:
                raise DomainError(409, "import_saving", "本项正在保存，请稍后获取结果")
            if body.target_card_id:
                if not body.update_confirmed or body.target_revision is None:
                    raise DomainError(
                        422, "import_target_confirmation", "请先查看目标与差异，再确认更新草稿"
                    )
                require_card(db, body.target_card_id)
                revision_matches(db.get(CardDraft, body.target_card_id), body.target_revision)
            content = normalize(body.content)
            validate_source_media(db, batch, item, content)
            item.content = content
            item.selected = body.selected
            item.target_card_id = body.target_card_id
            item.target_revision = body.target_revision
            item.revision += 1
            previous_job_id = item.job_id
            item.job_id = None
            touch_batch(
                batch,
                request.app.state.clock,
                db=db,
                job_ids=[previous_job_id] if previous_job_id else (),
            )
            db.flush()
            return item_view(db, item)

        return operate(
            db,
            admin,
            "admin",
            key,
            "import.stage:" + item_id,
            body.model_dump(exclude_unset=True),
            now,
            execute,
        )

    @router.get("/imports/{batch_id}/confirmation", response_model=ImportConfirmation)
    def review(
        batch_id: str,
        item_ids: Annotated[list[str] | None, Query()] = None,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        return confirmation(db, owned_batch(db, batch_id, admin.id), item_ids)

    @router.post("/imports/{batch_id}/save", response_model=ImportBatchView)
    def save(
        batch_id: str,
        body: AcceptSave,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        now = request.app.state.clock()

        def execute():
            batch = owned_batch(db, batch_id, admin.id)
            current = confirmation(db, batch, body.item_ids)
            if current["version"] != body.version:
                raise DomainError(409, "import_changed", "核对资料或范围已变化，请重新确认")
            if not current["count"]:
                raise DomainError(422, "import_selection_empty", "请先选择可以保存的卡片")
            items = db.scalars(
                select(ImportItem)
                .where(ImportItem.batch_id == batch_id)
                .order_by(ImportItem.position, ImportItem.id)
            ).all()
            previous_job_ids = set()
            for item in items:
                value = item_view(db, item)
                if (
                    (body.item_ids is not None and item.id not in body.item_ids)
                    or not item.selected
                    or not item.readable
                    or value["state"] in {"saved", "duplicate", "saving"}
                ):
                    continue
                if item.job_id:
                    previous_job_ids.add(item.job_id)
                item.job_id = enqueue(
                    db,
                    "import.save",
                    "admin",
                    admin.id,
                    {
                        "item_id": item.id,
                        "revision": item.revision,
                        "content": item.content,
                        "target_card_id": item.target_card_id,
                        "target_revision": item.target_revision,
                    },
                    now,
                    settings=request.app.state.settings,
                ).id
            touch_batch(batch, request.app.state.clock, db=db, job_ids=previous_job_ids)
            db.flush()
            return batch_view(db, batch, request.app.state.settings)

        return operate(
            db,
            admin,
            "admin",
            key,
            "import.save:" + batch_id,
            body.model_dump(exclude_unset=True),
            now,
            execute,
        )

    return router
