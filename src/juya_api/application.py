"""Common lifecycle and health, without mixing role-specific routes."""

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from .config import Settings
from .database import make_database, naive_utc
from .errors import DomainError, install_errors


def application(role: str, settings: Settings, sessions=None, clock=None) -> FastAPI:
    """Build an isolated entrypoint with explicit dependencies and no implicit schema writes."""
    app = FastAPI(
        title=f"Juya {role} API",
        version="1.5.0",
        docs_url="/docs" if settings.environment != "production" else None,
    )
    if sessions is None:
        _, sessions = make_database(settings)
    app.state.settings, app.state.sessions = settings, sessions
    app.state.clock = lambda: naive_utc(clock() if clock else datetime.now(UTC))
    app.state.role = role
    install_errors(app)
    if settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins,
            allow_credentials=role == "admin",
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"],
            allow_headers=[
                "Authorization",
                "Content-Type",
                "X-CSRF-Token",
                "Idempotency-Key",
                "Range",
            ],
        )

    @app.get("/health/live", include_in_schema=False)
    def live():
        return {"status": "live", "service": role}

    @app.get("/health/ready", include_in_schema=False)
    def ready():
        with sessions() as db:
            db.execute(text("SELECT 1"))
            if not inspect(db.get_bind()).has_table("users"):
                raise DomainError(503, "schema_not_ready", "数据库尚未初始化")
        return {"status": "ready", "service": role, "environment": settings.environment}

    return app
