"""Common lifecycle and health, without mixing role-specific routes."""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from . import job_models  # noqa: F401
from .config import Settings
from .database import make_database, naive_utc
from .errors import install_errors
from .response_contracts import ErrorResponse
from .schema import require_compatible_schema


def application(role: str, settings: Settings, sessions=None, clock=None) -> FastAPI:
    """Build an isolated entrypoint with explicit dependencies and no implicit schema writes."""
    if settings.image_role and settings.image_role != role:
        raise ValueError("API role must match the image role")
    app = FastAPI(
        title=f"Juya {role} API",
        responses={
            code: {"model": ErrorResponse}
            for code in [400, 401, 403, 404, 409, 410, 422, 429, 500, 503]
        },
        version="1.5.0",
        docs_url="/docs" if settings.environment != "production" else None,
    )
    if sessions is None:
        _, sessions = make_database(settings)
    app.state.settings, app.state.sessions = settings, sessions
    app.state.clock = lambda: naive_utc(clock() if clock else datetime.now(UTC))
    app.state.role = role
    install_errors(app)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    @app.middleware("http")
    async def private_responses(request, call_next):
        request.state.request_id = str(uuid.uuid4())
        try:
            response = await call_next(request)
        except Exception as error:
            # Exception strings and tracebacks can include upstream URLs,
            # submitted contacts or database values. Record only correlation
            # metadata; domain/validation failures are handled separately.
            logging.getLogger("juya.requests").error(
                "request_failed role=%s request_id=%s exception_type=%s",
                role,
                request.state.request_id,
                type(error).__name__,
            )
            response = JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "internal_error",
                        "message": "服务暂未完成请求，请重试以确认结果",
                        "details": None,
                    },
                    "request_id": request.state.request_id,
                },
            )
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Request-ID"] = request.state.request_id
        return response

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
            if db.get_bind().dialect.name == "sqlite":
                db.connection(execution_options={"sqlite_write_intent": False})
            db.execute(text("SELECT 1"))
            require_compatible_schema(db, minimum_revision=15)
        return {"status": "ready", "service": role, "environment": settings.environment}

    return app
