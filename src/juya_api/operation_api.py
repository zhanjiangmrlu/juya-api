"""Role-scoped durable write receipts; never an unauthenticated result lookup."""

import json
from typing import Literal

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .content_models import Operation
from .dependencies import administrator, database, learner
from .errors import DomainError
from .response_contracts import OperationResponse
from .security import decrypt, digest


def routes(role: Literal["admin", "mini"]):
    router = APIRouter(prefix=f"/api/{role}/v1", tags=["durable write results"])

    @router.get("/operations/{key}", response_model=OperationResponse)
    def operation(
        key: str,
        request: Request,
        actor=Depends(administrator if role == "admin" else learner),
        db: Session = Depends(database, scope="function"),
    ):
        row = db.get(Operation, (role + ":" + actor.id, digest(key)))
        if not row:
            raise DomainError(404, "operation_unknown", "尚未查询到成功结果，请核对后重试")
        return {
            "status": "succeeded",
            "result": json.loads(decrypt(request.app.state.settings, row.result) or "{}"),
        }

    return router
