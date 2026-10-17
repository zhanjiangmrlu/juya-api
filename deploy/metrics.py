"""Read aggregate queue, TTS and SQL metrics inside a configured API container."""

import json
from datetime import timedelta

from sqlalchemy import func, select, text

from juya_api.config import Settings
from juya_api.database import make_database, naive_utc, utc_now
from juya_api.job_models import Job


def snapshot(db, now, *, connections):
    pending = db.scalar(
        select(func.count()).select_from(Job).where(Job.state.in_(["queued", "retry"]))
    )
    oldest = db.scalar(
        select(func.min(Job.available_at)).where(
            Job.state.in_(["queued", "retry"]), Job.available_at <= now
        )
    )
    expired = db.scalar(
        select(func.count())
        .select_from(Job)
        .where(Job.state == "running", Job.lease_expires_at < now)
    )
    states = dict(
        db.execute(
            select(Job.state, func.count())
            .where(
                Job.kind == "tts.synthesize",
                Job.state.in_(["succeeded", "failed"]),
                Job.updated_at >= now - timedelta(minutes=15),
            )
            .group_by(Job.state)
        ).all()
    )
    return {
        "available": True,
        "connections": connections,
        "pending_jobs": pending,
        "oldest_pending_seconds": max(0, (now - naive_utc(oldest)).total_seconds())
        if oldest
        else 0,
        "expired_leases": expired,
        "tts_completed": sum(states.values()),
        "tts_failed": states.get("failed", 0),
    }


def main():
    try:
        settings = Settings()
        engine, sessions = make_database(settings)
        try:
            with sessions() as db:
                connections = int(
                    db.execute(text("SHOW GLOBAL STATUS LIKE 'Threads_connected'")).one()[1]
                )
                value = snapshot(db, utc_now(), connections=connections)
        finally:
            engine.dispose()
        print(json.dumps(value))
    except Exception:
        print(json.dumps({"available": False}))


if __name__ == "__main__":
    main()
