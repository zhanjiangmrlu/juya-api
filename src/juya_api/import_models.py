"""Recoverable import source files, editable review staging and per-card save results."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime
from .models import identifier


class ImportBatch(Base):
    __tablename__ = "import_batches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    admin_id: Mapped[str] = mapped_column(ForeignKey("administrators.id"), index=True)
    mode: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    updated_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, default=lambda context: context.get_current_parameters()["created_at"]
    )


class ImportFile(Base):
    __tablename__ = "import_files"
    __table_args__ = (
        UniqueConstraint("batch_id", "parent_id", "name", "sha256", name="uq_import_file_object"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id"), index=True)
    parent_id: Mapped[str] = mapped_column(String(36), default="")
    name: Mapped[str] = mapped_column(String(512))
    kind: Mapped[str] = mapped_column(String(16))
    storage_key: Mapped[str] = mapped_column(String(255))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    media_id: Mapped[str | None] = mapped_column(ForeignKey("media.id"))
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"))
    error_code: Mapped[str | None] = mapped_column(String(64))
    progress: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)


class ImportItem(Base):
    __tablename__ = "import_items"
    __table_args__ = (
        UniqueConstraint("source_file_id", "source_index", name="uq_import_source_section"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id"), index=True)
    source_file_id: Mapped[str] = mapped_column(ForeignKey("import_files.id"))
    source_index: Mapped[int] = mapped_column(Integer)
    source_identity: Mapped[str] = mapped_column(String(64))
    content: Mapped[dict] = mapped_column(JSON)
    parser_issues: Mapped[list] = mapped_column(JSON, default=list)
    readable: Mapped[bool] = mapped_column(Boolean, default=True)
    selected: Mapped[bool] = mapped_column(Boolean, default=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    target_card_id: Mapped[str | None] = mapped_column(ForeignKey("cards.id"))
    target_revision: Mapped[int | None] = mapped_column(Integer)
    saved_card_id: Mapped[str | None] = mapped_column(ForeignKey("cards.id"))
    saved_draft_revision: Mapped[int | None] = mapped_column(Integer)
    last_saved_hash: Mapped[str | None] = mapped_column(String(64))
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"))
    position: Mapped[int] = mapped_column(Integer)


class ImportIdentity(Base):
    __tablename__ = "import_identities"
    object_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("cards.id"))
    content_hash: Mapped[str] = mapped_column(String(64))
    draft_revision: Mapped[int] = mapped_column(Integer)
