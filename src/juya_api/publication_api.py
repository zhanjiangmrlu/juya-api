"""Optimistic catalog ordering and resumable per-card publication acceptance."""

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .content_models import Card, CardDraft, CardVersion, Media, SettingCounter
from .content_service import require_card, reviewed_candidate
from .database import timestamp
from .dependencies import administrator, database, operation_key
from .errors import DomainError
from .job_models import Job
from .jobs import enqueue
from .publication_models import PublicationBatch, PublicationItem
from .security import fingerprint
from .transactions import operate


class OrderedCard(BaseModel):
    id: str
    name: str
    title_en: str = ""
    image_id: str | None
    thumbnail_id: str | None = None


class CatalogOrder(BaseModel):
    version: str
    items: list[OrderedCard]


class SaveOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str = Field(min_length=64, max_length=64)
    card_ids: list[str] = Field(max_length=10000)


class SelectedPublication(BaseModel):
    model_config = ConfigDict(extra="forbid")
    card_id: str = Field(max_length=36)
    revision: int = Field(ge=1)
    preview_id: str = Field(max_length=36)


class CreateBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: Literal[True]
    items: list[SelectedPublication] = Field(min_length=1, max_length=50)


class PublicationResult(BaseModel):
    id: str
    card_id: str
    name: str
    title_en: str = ""
    state: str
    error_code: str | None
    job_id: str


class BatchView(BaseModel):
    id: str
    created_at: str
    items: list[PublicationResult]


def catalog(db):
    """Read one ordered publication set; this digest changes on reorder/membership changes."""
    rows = db.execute(
        select(Card.id, Card.sort_order, CardVersion.payload)
        .join(CardVersion, Card.current_version_id == CardVersion.id)
        .where(Card.status == "published", Card.deleted_at.is_(None))
        .order_by(Card.sort_order, Card.id)
    ).all()
    thumbnails = dict(
        db.execute(
            select(Media.id, Media.thumbnail_id).where(
                Media.id.in_([r.payload["image_id"] for r in rows if r.payload["image_id"]])
            )
        ).all()
    )
    generation = db.get(SettingCounter, "catalog_revision")
    return {
        "version": fingerprint(
            {
                "generation": generation.value if generation else 0,
                "items": [(r.id, r.sort_order) for r in rows],
            }
        ),
        "items": [
            {
                "id": r.id,
                "name": r.payload["name"],
                "title_en": r.payload.get("title_en", ""),
                "image_id": r.payload["image_id"],
                "thumbnail_id": thumbnails.get(r.payload["image_id"]),
            }
            for r in rows
        ],
    }


def owned_batch(db, batch_id, admin_id):
    """Keep accepted work visible only to its administrator."""
    row = db.get(PublicationBatch, batch_id)
    if not row or row.admin_id != admin_id:
        raise DomainError(404, "batch_missing", "未找到本次发布")
    return row


def batch_view(db, batch):
    """Derive each receipt from its durable job, including crash-terminal failures."""
    rows = db.execute(
        select(PublicationItem, Job)
        .join(Job, PublicationItem.job_id == Job.id)
        .where(PublicationItem.batch_id == batch.id)
        .order_by(PublicationItem.position)
    ).all()
    return {
        "id": batch.id,
        "created_at": timestamp(batch.created_at),
        "items": [
            {
                "id": item.id,
                "card_id": item.card_id,
                "name": item.name,
                "title_en": item.title_en,
                "state": job.state,
                "error_code": job.error_code,
                "job_id": job.id,
            }
            for item, job in rows
        ],
    }


def publication_job(db, settings, admin_id, item, now):
    """Use frozen review identities, never the latest draft implicitly."""
    job = enqueue(
        db,
        "card.publish",
        "admin",
        admin_id,
        {"card_id": item.card_id, "revision": item.revision, "preview_id": item.preview_id},
        now,
        settings=settings,
    )
    item.job_id = job.id


def routes():
    router = APIRouter(prefix="/api/admin/v1", tags=["ordering and batch publication"])

    @router.get("/catalog-order", response_model=CatalogOrder)
    def read_order(admin=Depends(administrator), db: Session = Depends(database, scope="function")):
        return catalog(db)

    @router.put("/catalog-order", response_model=CatalogOrder)
    def save_order(
        body: SaveOrder,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        def execute():
            current = catalog(db)
            if current["version"] != body.version:
                raise DomainError(
                    409, "catalog_changed", "已发布卡片或顺序已变化，请重新获取后调整"
                )
            ids = [r["id"] for r in current["items"]]
            if len(body.card_ids) != len(set(body.card_ids)) or set(ids) != set(body.card_ids):
                raise DomainError(422, "catalog_incomplete", "请调整全部已发布卡片的完整顺序")
            for position, card_id in enumerate(body.card_ids):
                require_card(db, card_id).sort_order = position + 1
            db.flush()
            return catalog(db)

        return operate(
            db,
            admin,
            "admin",
            key,
            "catalog.order",
            body.model_dump(),
            request.app.state.clock(),
            execute,
        )

    @router.post("/publication-batches", status_code=201, response_model=BatchView)
    def create(
        body: CreateBatch,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        now = request.app.state.clock()

        def execute():
            if len({i.card_id for i in body.items}) != len(body.items):
                raise DomainError(422, "batch_duplicate", "同一张卡片只需选择一次")
            batch = PublicationBatch(admin_id=admin.id, created_at=now)
            db.add(batch)
            db.flush()
            for position, value in enumerate(body.items):
                draft = db.get(CardDraft, value.card_id)
                if draft is None:
                    raise DomainError(422, "batch_reference_invalid", "请选择可以核对的卡片")
                item = PublicationItem(
                    batch_id=batch.id,
                    card_id=value.card_id,
                    name=draft.payload["name"],
                    title_en=draft.payload.get("title_en", ""),
                    revision=value.revision,
                    preview_id=value.preview_id,
                    position=position,
                )
                publication_job(db, request.app.state.settings, admin.id, item, now)
                db.add(item)
            db.flush()
            return batch_view(db, batch)

        return operate(
            db, admin, "admin", key, "publication.batch", body.model_dump(), now, execute
        )

    @router.get("/publication-batches/{batch_id}", response_model=BatchView)
    def read(
        batch_id: str,
        admin=Depends(administrator),
        db: Session = Depends(database, scope="function"),
    ):
        return batch_view(db, owned_batch(db, batch_id, admin.id))

    @router.get("/publication-batches", response_model=list[BatchView])
    def recent(admin=Depends(administrator), db: Session = Depends(database, scope="function")):
        rows = db.scalars(
            select(PublicationBatch)
            .where(PublicationBatch.admin_id == admin.id)
            .order_by(PublicationBatch.created_at.desc(), PublicationBatch.id.desc())
            .limit(10)
        ).all()
        return [batch_view(db, row) for row in rows]

    @router.post("/publication-batches/{batch_id}/retry", response_model=BatchView)
    def retry(
        batch_id: str,
        request: Request,
        admin=Depends(administrator),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        now = request.app.state.clock()

        def execute():
            batch = owned_batch(db, batch_id, admin.id)
            rows = db.execute(
                select(PublicationItem, Job)
                .join(Job, PublicationItem.job_id == Job.id)
                .where(PublicationItem.batch_id == batch.id, Job.state == "failed")
            ).all()
            for item, previous in rows:
                try:
                    reviewed_candidate(
                        db,
                        require_card(db, item.card_id),
                        admin.id,
                        item.revision,
                        item.preview_id,
                        now,
                    )
                except DomainError as error:
                    previous.error_code = error.code
                    continue
                publication_job(db, request.app.state.settings, admin.id, item, now)
            db.flush()
            return batch_view(db, batch)

        return operate(db, admin, "admin", key, "publication.retry:" + batch_id, {}, now, execute)

    return router
