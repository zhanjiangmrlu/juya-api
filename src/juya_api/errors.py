"""Safe public errors that do not echo credentials or submitted personal data."""

import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class DomainError(Exception):
    def __init__(self, status: int, code: str, message: str, details=None):
        super().__init__(code)
        self.status, self.code, self.message, self.details = status, code, message, details


def install_errors(app: FastAPI):
    """Register typed domain failures and sanitize request validation errors."""

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError):
        return JSONResponse(
            status_code=exc.status,
            content={
                "error": {"code": exc.code, "message": exc.message, "details": exc.details},
                "request_id": getattr(request.state, "request_id", str(uuid.uuid4())),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_request",
                    "message": "请检查填写内容",
                    "details": [
                        {"field": ".".join(str(x) for x in e["loc"]), "message": e["msg"]}
                        for e in exc.errors()
                    ],
                }
            },
        )
