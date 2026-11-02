"""Explicit local publication warmup; dry-run never accepts tasks or calls a provider."""

import argparse
import json
from datetime import UTC, datetime

from sqlalchemy import select, true
from sqlalchemy.engine import make_url

from .config import Settings
from .content_models import Card, CardVersion
from .content_service import catalog_lock
from .database import make_database, naive_utc
from .dictionary import body_references, controlled_target
from .job_models import Job
from .models import Administrator, Audit
from .pronunciation import enqueue_prewarm, status
from .pronunciation_models import Pronunciation
from .transactions import actor_lock


def backfill(settings, sessions, card_ids, now, *, execute=False):
    """Only explicitly named current local publications can be accepted for generation."""
    if execute:
        url = make_url(settings.database_url)
        local = url.drivername.startswith("sqlite") or url.host in {"127.0.0.1", "localhost", "::1"}
        if settings.environment != "local" or not local:
            raise ValueError("execute requires the local environment and a local database")
        if not card_ids:
            raise ValueError("execute requires explicit card IDs")
    with sessions.begin() as db:
        publishers = {}
        if execute:
            for card_id in sorted(set(card_ids)):
                publisher = db.scalar(
                    select(Audit.admin_id)
                    .where(
                        Audit.action == "card.publish",
                        Audit.object_id == card_id,
                    )
                    .order_by(Audit.occurred_at.desc(), Audit.id.desc())
                    .limit(1)
                )
                if not publisher:
                    raise ValueError("every selected card requires an existing publication")
                publishers[card_id] = publisher
            for admin_id in sorted(set(publishers.values())):
                actor_lock(db, db.get(Administrator, admin_id), "admin")
            catalog_lock(db)
        cards = db.scalars(
            select(Card)
            .where(
                Card.deleted_at.is_(None),
                Card.status == "published",
                Card.id.in_(card_ids) if card_ids else true(),
            )
            .order_by(Card.id)
            .execution_options(populate_existing=True)
        ).all()
        if card_ids and {row.id for row in cards} != set(card_ids):
            raise ValueError("every selected card must be currently published")
        report = []
        for card in cards:
            if execute:
                enqueue_prewarm(
                    db,
                    settings,
                    card.id,
                    card.current_version_id,
                    publishers[card.id],
                    now,
                    revive=True,
                )
            report.append(
                {
                    "card_id": card.id,
                    "version_id": card.current_version_id,
                    "enqueued": execute,
                    **estimate(db, settings, card),
                }
            )
        return report


def estimate(db, settings, card):
    """Count unique actual readings and distinguish pending work from new provider attempts."""
    version = db.get(CardVersion, card.current_version_id)
    keys = set()
    skipped = 0
    for ref in body_references(version.payload, version.id):
        target = controlled_target(db, settings, card.id, ref)
        if target.reading:
            keys.add(target.cache_key)
        else:
            skipped += 1
    ready, processing = 0, 0
    for cache_key in keys:
        state = status(db, cache_key)["state"]
        if state == "ready":
            ready += 1
        else:
            cache = db.get(Pronunciation, cache_key)
            job = db.get(Job, cache.job_id) if cache and cache.job_id else None
            if job and job.state in {"queued", "retry", "running"}:
                processing += 1
    return {
        "word_count": len(keys),
        "ready_count": ready,
        "processing_count": processing,
        "to_generate_count": len(keys) - ready - processing,
        "skipped_reference_count": skipped,
    }


def main():
    """Show candidates by default; execution only accepts durable jobs, never inline cloud work."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--card-id", action="append", default=[])
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    engine, sessions = make_database(settings)
    try:
        print(
            json.dumps(
                backfill(
                    settings,
                    sessions,
                    args.card_id,
                    naive_utc(datetime.now(UTC)),
                    execute=args.execute,
                ),
                ensure_ascii=False,
            )
        )
    except ValueError as error:
        parser.error(str(error))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
