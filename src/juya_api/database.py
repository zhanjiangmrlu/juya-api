"""One schema, separate application sessions and independently versioned entrypoints."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import Settings


def utc_now() -> datetime:
    """Store UTC without timezone decoration consistently on MySQL and SQLite."""
    return datetime.now(UTC).replace(tzinfo=None)


def naive_utc(value: datetime) -> datetime:
    """Normalize an injected or provider timestamp before database comparisons."""
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value


def timestamp(value: datetime | None) -> str | None:
    """Serialize persisted UTC timestamps without depending on host timezone."""
    return value.isoformat(timespec="microseconds") + "Z" if value else None


UTCDateTime = DateTime().with_variant(DATETIME(fsp=6), "mysql")


class Base(DeclarativeBase):
    pass


def make_database(settings: Settings):
    """Create a bounded connection pool; SQLite is only for isolated local tests."""
    options: dict[str, Any] = {"pool_pre_ping": True, "hide_parameters": True}
    if settings.database_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    else:
        options.update(
            pool_size=5, max_overflow=3, pool_recycle=1800, isolation_level="READ COMMITTED"
        )
    engine = create_engine(settings.database_url, **options)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def foreign_keys(connection, _):
            # sqlite3's legacy SELECT/savepoint transaction handling can commit a
            # reservation before its parent operation. Let SQLAlchemy own BEGIN.
            connection.isolation_level = None
            connection.execute("PRAGMA foreign_keys=ON")

        @event.listens_for(engine, "begin")
        def begin_transaction(connection):
            connection.exec_driver_sql("BEGIN")

    return engine, sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
