"""Additive listening domain; scene identities and historic facts remain untouched."""

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime, utc_now
from .models import identifier


class ListeningCategory(Base):
    __tablename__ = "listening_categories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    name: Mapped[str] = mapped_column(String(160))
    name_en: Mapped[str] = mapped_column(String(300), default="", server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class ListeningTopic(Base):
    __tablename__ = "listening_topics"
    name_en: Mapped[str] = mapped_column(String(300), default="", server_default="")
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    category_id: Mapped[str] = mapped_column(ForeignKey("listening_categories.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(String(2000), default="", server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class ListeningArticle(Base):
    __tablename__ = "listening_articles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    topic_id: Mapped[str] = mapped_column(ForeignKey("listening_topics.id"), index=True)
    draft_topic_id: Mapped[str | None] = mapped_column(ForeignKey("listening_topics.id"))
    draft_topic_order: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    version_id: Mapped[str | None] = mapped_column(String(36))
    payload: Mapped[dict] = mapped_column(JSON)
    topic_order: Mapped[int] = mapped_column(Integer, default=0)
    global_order: Mapped[int] = mapped_column(Integer, default=0)
    batch_id: Mapped[str | None] = mapped_column(String(36), index=True)
    source_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)


class ListeningVersion(Base):
    __tablename__ = "listening_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    article_id: Mapped[str] = mapped_column(ForeignKey("listening_articles.id"), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    input_hash: Mapped[str | None] = mapped_column(String(64))
    published_at: Mapped[datetime] = mapped_column(UTCDateTime)


class ListeningPolicy(Base):
    __tablename__ = "listening_policy"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    free_count: Mapped[int | None] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    catalog_revision: Mapped[int] = mapped_column(Integer, default=0)


class ListeningFavorite(Base):
    __tablename__ = "listening_favorites"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    article_id: Mapped[str] = mapped_column(ForeignKey("listening_articles.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)


class ListeningCompletion(Base):
    __tablename__ = "listening_completions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    article_id: Mapped[str] = mapped_column(ForeignKey("listening_articles.id"), primary_key=True)
    first_completed_at: Mapped[datetime] = mapped_column(UTCDateTime)
    last_completed_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    first_version_id: Mapped[str] = mapped_column(ForeignKey("listening_versions.id"))
    last_version_id: Mapped[str] = mapped_column(ForeignKey("listening_versions.id"))


class ListeningDaily(Base):
    __tablename__ = "listening_daily"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    article_id: Mapped[str] = mapped_column(ForeignKey("listening_articles.id"), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True, index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("listening_versions.id"))
    accepted_at: Mapped[datetime] = mapped_column(UTCDateTime)


class ListeningProgress(Base):
    __tablename__ = "listening_progress"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    article_id: Mapped[str] = mapped_column(ForeignKey("listening_articles.id"), primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("listening_versions.id"), primary_key=True)
    reading_position: Mapped[int] = mapped_column(Integer)
    translation_open: Mapped[bool] = mapped_column(Boolean)
    audio_position: Mapped[float] = mapped_column(Float)
    playback_rate: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)


class ListeningTimeline(Base):
    __tablename__ = "listening_timelines"
    input_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    body_en: Mapped[str] = mapped_column(Text)
    audio_id: Mapped[str] = mapped_column(ForeignKey("media.id"))
    state: Mapped[str] = mapped_column(String(24), default="pending")
    words: Mapped[list] = mapped_column(JSON, default=list)
    job_id: Mapped[str | None] = mapped_column(String(36))
    error_code: Mapped[str | None] = mapped_column(String(64))
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("administrators.id"))


class ListeningJob(Base):
    """Own durable queue/leases, deliberately invisible to the existing scene worker."""

    __tablename__ = "listening_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    input_hash: Mapped[str] = mapped_column(
        ForeignKey("listening_timelines.input_hash"), index=True
    )
    state: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    provider_task_id: Mapped[str | None] = mapped_column(String(128))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(UTCDateTime)
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)


class ListeningImport(Base):
    __tablename__ = "listening_imports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    admin_id: Mapped[str] = mapped_column(ForeignKey("administrators.id"), index=True)
    mode: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(24), default="review")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    packages: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)


class ListeningCandidate(Base):
    __tablename__ = "listening_candidates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    batch_id: Mapped[str] = mapped_column(ForeignKey("listening_imports.id"), index=True)
    package_id: Mapped[str] = mapped_column(String(36))
    path: Mapped[str] = mapped_column(String(512))
    state: Mapped[str] = mapped_column(String(24))
    payload: Mapped[dict] = mapped_column(JSON)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("listening_topics.id"))
    source_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    errors: Mapped[list] = mapped_column(JSON, default=list)
    resources: Mapped[dict] = mapped_column(JSON, default=dict)
    article_id: Mapped[str | None] = mapped_column(ForeignKey("listening_articles.id"))
    duplicate_of: Mapped[str | None] = mapped_column(String(36))
    removed: Mapped[bool] = mapped_column(Boolean, default=False)
