"""One synthesis identity per spelling, confirmed reading and provider configuration."""

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime


class Pronunciation(Base):
    __tablename__ = "pronunciations"
    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    spelling: Mapped[str] = mapped_column(String(300))
    reading: Mapped[str] = mapped_column(String(300))
    configuration: Mapped[dict] = mapped_column(JSON)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"))
    media_id: Mapped[str | None] = mapped_column(ForeignKey("media.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
