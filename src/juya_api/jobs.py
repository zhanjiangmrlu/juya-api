"""A broker delivery is a hint; durable state and ownership live in MySQL."""

import json
from datetime import timedelta

from sqlalchemy import and_, or_, select

from .job_models import Job
from .models import identifier
from .security import decrypt, encrypt


def enqueue(db, kind, owner_kind, owner_id, payload, now, *, settings):
    """Accept a job in its caller's transaction; production task payloads are encrypted."""
    value = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    job = Job(
        id=identifier(),
        kind=kind,
        owner_kind=owner_kind,
        owner_id=owner_id,
        payload=encrypt(settings, value),
        state="queued",
        attempts=0,
        max_attempts=3,
        available_at=now,
        dispatch_after=now,
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.flush()
    return job


def dispatch(sessions, now, publish, *, limit=50):
    """Recover missed deliveries and expired workers; failed broker writes stay due."""
    sent = 0
    with sessions.begin() as db:
        rows = db.scalars(
            select(Job)
            .where(
                Job.dispatch_after <= now,
                or_(
                    and_(Job.state.in_(["queued", "retry"]), Job.available_at <= now),
                    and_(Job.state == "running", Job.lease_expires_at <= now),
                ),
            )
            .order_by(Job.created_at, Job.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        for row in rows:
            try:
                publish(row.id)
            except Exception:
                # Never store broker URLs, task payloads or provider exception text.
                continue
            row.dispatch_after = now + timedelta(seconds=30)
            sent += 1
    return sent


def claim(sessions, job_id, now, *, settings):
    """Claim once under a row lock, recovering a crashed worker after five minutes."""
    with sessions.begin() as db:
        row = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if not row or row.state in {"succeeded", "failed"}:
            return None
        if row.available_at > now or (row.state == "running" and row.lease_expires_at > now):
            return None
        if row.attempts >= row.max_attempts:
            row.state, row.error_code, row.updated_at = "failed", "worker_interrupted", now
            return None
        row.attempts += 1
        row.lease = identifier()
        row.lease_expires_at = now + timedelta(minutes=5)
        row.state, row.updated_at = "running", now
        payload = decrypt(settings, row.payload)
        return {
            "id": row.id,
            "kind": row.kind,
            "payload": json.loads(payload or "{}"),
            "attempt": row.attempts,
            "lease": row.lease,
            "owner_kind": row.owner_kind,
            "owner_id": row.owner_id,
        }


def finish(sessions, job_id, lease, now, result, *, apply=None):
    """Commit side effects and the terminal receipt together; a stale worker cannot write."""
    with sessions.begin() as db:
        row = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if not row or row.state != "running" or row.lease != lease or row.lease_expires_at < now:
            return False
        if apply:
            apply(db, row)
        row.state, row.result, row.updated_at = "succeeded", result, now
        row.error_code, row.lease, row.lease_expires_at = None, None, None
        return True


def fail(sessions, job_id, lease, now, code, *, temporary=False, apply=None):
    """Retry only classified temporary failures, at most twice, using sanitized codes."""
    if not code.replace("_", "").isalnum() or len(code) > 64:
        code = "task_failed"
    with sessions.begin() as db:
        row = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if not row or row.state != "running" or row.lease != lease or row.lease_expires_at < now:
            return False
        retry = temporary and row.attempts < row.max_attempts
        row.state = "retry" if retry else "failed"
        row.available_at = now + timedelta(seconds=10 * row.attempts)
        row.dispatch_after = row.available_at
        row.error_code, row.updated_at = code, now
        row.lease, row.lease_expires_at = None, None
        if apply:
            apply(db, row)
        return True
