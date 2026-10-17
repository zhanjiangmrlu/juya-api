"""One persistent operation result per authenticated actor and request key."""

from sqlalchemy import select

from .content_models import Operation
from .errors import DomainError
from .models import Administrator, User
from .security import digest, fingerprint


def actor_lock(db, actor, role: str):
    """Serialize one learner's statistics or one administrator's writes in MySQL."""
    model = Administrator if role == "admin" else User
    return db.scalar(
        select(model)
        .where(model.id == actor.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def operate(db, actor, role: str, key: str, action: str, payload, now, execute):
    """Replay committed outcomes before rechecking mutable state such as day/version."""
    actor_lock(db, actor, role)
    scope = role + ":" + actor.id
    identity = (scope, digest(key))
    request_hash = fingerprint({"action": action, "payload": payload})
    previous = db.get(Operation, identity)
    if previous:
        if previous.fingerprint != request_hash:
            raise DomainError(409, "operation_conflict", "操作内容已变化，请重新确认")
        return previous.result
    result = execute()
    db.add(
        Operation(
            scope=scope,
            key_digest=identity[1],
            action=action,
            fingerprint=request_hash,
            result=result,
            accepted_at=now,
        )
    )
    db.flush()
    return result
