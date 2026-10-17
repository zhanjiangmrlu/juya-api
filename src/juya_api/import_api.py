"""Same-page upload/review/save workflow backed by persistent batches and item receipts."""

import hashlib
from pathlib import PurePosixPath
from typing import Literal

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .content_contracts import SceneContent
from .content_models import CardDraft
from .content_service import normalize, require_card, revision_matches
from .dependencies import administrator, database, operation_key
from .errors import DomainError
from .import_models import ImportBatch, ImportFile, ImportItem
from .import_service import (
    batch_view,
    confirmation,
    file_view,
    item_job,
    item_view,
    owned_batch,
    resolve,
)
from .jobs import enqueue
from .media_api import save_media
from .models import identifier
from .response_contracts import FieldIssue
from .storage import ObjectStorage
from .transactions import operate


class CreateImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["zip", "docx"]


class ImportFileView(BaseModel):
    id: str
    name: str
    kind: str
    size: int
    media_id: str | None
    state: str
    job_id: str | None
    error_code: str | None
    parent_id: str


class ImportItemView(BaseModel):
    id: str
    revision: int
    content: SceneContent
    selected: bool
    readable: bool
    state: str
    issues: list[FieldIssue]
    source_file_id: str
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
            batch = ImportBatch(admin_id=admin.id, mode=body.mode, created_at=now)
            db.add(batch)
            db.flush()
            return batch_view(db, batch)

        return operate(db, admin, "admin", key, "import.create", body.model_dump(), now, execute)

    @router.get("/imports", response_model=list[ImportBatchView])
    def recent(admin=Depends(administrator), db: Session = Depends(database, scope="function")):
        rows = db.scalars(
            select(ImportBatch)
            .where(ImportBatch.admin_id == admin.id)
            .order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc())
            .limit(5)
        ).all()
        return [batch_view(db, batch) for batch in rows]

    @router.get("/imports/{batch_id}", response_model=ImportBatchView)
    def read(
        batch_id: str,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        return batch_view(db, owned_batch(db, batch_id, admin.id))

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
        if (batch.mode == "zip" and kind != "zip") or (batch.mode == "docx" and kind == "zip"):
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
            previous = db.scalar(
                select(ImportFile).where(
                    ImportFile.batch_id == batch_id,
                    ImportFile.parent_id == "",
                    ImportFile.name == name,
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
                medium = save_media(db, settings, admin, "admin", kind, data, now)
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
            lambda: resolve(db, owned_batch(db, batch_id, admin.id)),
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
            owned_batch(db, batch_id, admin.id)
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
            item.content = normalize(body.content)
            item.selected = body.selected
            item.target_card_id = body.target_card_id
            item.target_revision = body.target_revision
            item.revision += 1
            item.job_id = None
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
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        return confirmation(db, owned_batch(db, batch_id, admin.id))

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
            current = confirmation(db, batch)
            if current["version"] != body.version:
                raise DomainError(409, "import_changed", "核对资料或范围已变化，请重新确认")
            if not current["count"]:
                raise DomainError(422, "import_selection_empty", "请先选择可以保存的卡片")
            items = db.scalars(
                select(ImportItem)
                .where(ImportItem.batch_id == batch_id)
                .order_by(ImportItem.position, ImportItem.id)
            ).all()
            for item in items:
                value = item_view(db, item)
                if (
                    not item.selected
                    or not item.readable
                    or value["state"] in {"saved", "duplicate", "saving"}
                ):
                    continue
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
            db.flush()
            return batch_view(db, batch)

        return operate(
            db, admin, "admin", key, "import.save:" + batch_id, body.model_dump(), now, execute
        )

    return router
