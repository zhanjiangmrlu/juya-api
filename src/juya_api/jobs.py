"""A broker delivery is a hint; durable state and ownership live in MySQL."""

import json
from datetime import timedelta

from sqlalchemy import and_, case, or_, select, true

from .job_models import Job
from .models import Administrator, User, identifier
from .security import decrypt, encrypt
from .transactions import actor_lock


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


def dispatch(sessions, now, publish, *, limit=50, role=None):
    """Recover missed deliveries and expired workers; failed broker writes stay due."""
    sent = 0
    with sessions.begin() as db:
        rows = db.scalars(
            select(Job)
            .where(
                Job.owner_kind == role if role else true(),
                Job.kind != "tts.prewarm",
                Job.dispatch_after <= now,
                or_(
                    and_(Job.state.in_(["queued", "retry"]), Job.available_at <= now),
                    and_(Job.state == "running", Job.lease_expires_at <= now),
                ),
            )
            .order_by(
                case((Job.kind == "pronunciation.prewarm", 1), else_=0), Job.created_at, Job.id
            )
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
        for warm_role in [role] if role else ["admin", "mini"]:
            if sent >= limit:
                break
            prewarm_gate(db, warm_role)
            active = admitted_prewarm(db, warm_role)
            candidates = db.scalars(
                select(Job)
                .where(
                    Job.owner_kind == warm_role,
                    Job.kind == "tts.prewarm",
                    Job.id == active if active else true(),
                    Job.dispatch_after <= now,
                    or_(
                        and_(Job.state.in_(["queued", "retry"]), Job.available_at <= now),
                        and_(Job.state == "running", Job.lease_expires_at <= now),
                    ),
                )
                .order_by(Job.created_at, Job.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            ).all()
            for row in candidates:
                try:
                    publish(row.id)
                except Exception:
                    continue
                row.result = {**(row.result or {}), "admitted": True}
                row.dispatch_after = now + timedelta(seconds=30)
                sent += 1
    return sent


def claim(sessions, job_id, now, *, settings, role=None):
    """Claim once under a row lock, recovering a crashed worker after five minutes."""
    with sessions.begin() as db:
        lock_admin_job(db, job_id, role=role)
        hint = db.execute(select(Job.kind, Job.owner_kind).where(Job.id == job_id)).first()
        if hint and hint.kind == "tts.prewarm":
            if role and hint.owner_kind != role:
                return None
            prewarm_gate(db, hint.owner_kind)
            active = admitted_prewarm(db, hint.owner_kind)
            if active and active != job_id:
                return None
        row = db.scalar(
            select(Job)
            .where(Job.id == job_id, Job.owner_kind == role if role else true())
            .with_for_update()
        )
        if not row or row.state in {"succeeded", "failed"}:
            return None
        if row.available_at > now or (row.state == "running" and row.lease_expires_at > now):
            return None
        if row.attempts >= row.max_attempts:
            row.state, row.error_code, row.updated_at = "failed", "worker_interrupted", now
            touch_import_job(db, row, now)
            return None
        if row.kind == "tts.prewarm":
            row.result = {**(row.result or {}), "admitted": True}
        row.attempts += 1
        row.lease = identifier()
        row.lease_expires_at = now + timedelta(minutes=5)
        row.state, row.updated_at = "running", now
        touch_import_job(db, row, now)
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
        lock_admin_job(db, job_id)
        # Publication writers take catalog before their aggregate job. Match that
        # order so warmup cannot commit a revoked publication or deadlock it.
        kind = db.scalar(select(Job.kind).where(Job.id == job_id))
        if kind in {"pronunciation.prewarm", "tts.prewarm"}:
            from .content_service import catalog_lock

            catalog_lock(db)
        row = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if not row or row.state != "running" or row.lease != lease or row.lease_expires_at < now:
            return False
        if apply:
            apply(db, row)
        row.state, row.result, row.updated_at = "succeeded", result, now
        row.error_code, row.lease, row.lease_expires_at = None, None, None
        touch_import_job(db, row, now)
        return True


def fail(sessions, job_id, lease, now, code, *, temporary=False, apply=None):
    """Retry only classified temporary failures, at most twice, using sanitized codes."""
    if not code.replace("_", "").isalnum() or len(code) > 64:
        code = "task_failed"
    with sessions.begin() as db:
        lock_admin_job(db, job_id)
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
        touch_import_job(db, row, now)
        return True


def lock_admin_job(db, job_id, *, role=None):
    """Use actor→job→file ordering, shared with HTTP import writes and progress."""
    owner = db.execute(select(Job.owner_kind, Job.owner_id).where(Job.id == job_id)).first()
    if owner and owner.owner_kind in {"admin", "mini"} and role in {None, owner.owner_kind}:
        model = Administrator if owner.owner_kind == "admin" else User
        actor = db.get(model, owner.owner_id)
        if actor:
            actor_lock(db, actor, owner.owner_kind)


def touch_import_job(db, job, now):
    """Persist the deletion version with each referenced task transition."""
    if job.owner_kind != "admin" or job.kind not in {"import.parse", "import.save", "media.decode"}:
        return
    from .content_models import Media
    from .import_models import ImportBatch, ImportFile, ImportItem
    from .import_service import touch_batch

    ids = set(
        db.scalars(
            select(ImportFile.batch_id).where(
                or_(
                    ImportFile.job_id == job.id,
                    ImportFile.media_id.in_(select(Media.id).where(Media.job_id == job.id)),
                )
            )
        )
    )
    ids.update(db.scalars(select(ImportItem.batch_id).where(ImportItem.job_id == job.id)))
    for batch_id in sorted(ids):
        batch = db.get(ImportBatch, batch_id)
        if batch and batch.deleted_at is None:
            touch_batch(batch, now, db=db)


def prewarm_gate(db, role):
    """Serialize admission across dispatchers and direct/recovered worker deliveries."""
    from .content_models import SettingCounter
    from .persistence import insert_once

    name = "tts-prewarm-admission:" + role
    insert_once(db, SettingCounter, {"name": name, "value": 0}, ["name"])
    db.scalar(select(SettingCounter).where(SettingCounter.name == name).with_for_update())


def admitted_prewarm(db, role):
    """Retries and expired leases retain their role's slot until a terminal receipt."""
    return db.scalar(
        select(Job.id)
        .where(
            Job.kind == "tts.prewarm",
            Job.owner_kind == role,
            Job.state.in_(["queued", "retry", "running"]),
            Job.result["admitted"].as_boolean().is_(True),
        )
        .order_by(Job.created_at, Job.id)
        .limit(1)
    )
