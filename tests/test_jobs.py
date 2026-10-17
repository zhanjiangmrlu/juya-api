"""Durability at the database/broker and worker-restart boundaries."""

from datetime import timedelta

import pytest
from sqlalchemy import select


def api():
    try:
        from juya_api.job_models import Job
        from juya_api.jobs import claim, dispatch, enqueue, fail, finish
    except ImportError as error:
        pytest.fail(f"Durable task processing is missing: {error}")
    return claim, dispatch, enqueue, finish, fail, Job


def test_enqueue_rollback_and_broker_outage_recovery(system):
    claim, dispatch, enqueue, finish, fail, Job = api()
    sessions, now = system["sessions"], system["time"][0].replace(tzinfo=None)
    with pytest.raises(RuntimeError), sessions.begin() as db:
        enqueue(
            db,
            "media.decode",
            "admin",
            "actor",
            {"media_id": "one"},
            now,
            settings=system["settings"],
        )
        raise RuntimeError("rollback")
    with sessions() as db:
        assert db.scalars(select(Job)).all() == []
    with sessions.begin() as db:
        row = enqueue(
            db,
            "media.decode",
            "admin",
            "actor",
            {"media_id": "one"},
            now,
            settings=system["settings"],
        )
        job_id = row.id

    def unavailable(_):
        raise ConnectionError("redis unavailable")

    assert dispatch(sessions, now, unavailable) == 0
    delivered = []
    assert dispatch(sessions, now + timedelta(seconds=1), delivered.append) == 1
    assert delivered == [job_id]
    with sessions() as db:
        assert db.get(Job, job_id).state == "queued"


def test_role_scoped_dispatch_and_claim_never_execute_the_other_api_tasks(system):
    claim, dispatch, enqueue, finish, fail, Job = api()
    sessions, now = system["sessions"], system["time"][0].replace(tzinfo=None)
    with sessions.begin() as db:
        ids = {
            role: enqueue(
                db,
                "media.decode",
                role,
                "actor",
                {"media_id": role},
                now,
                settings=system["settings"],
            ).id
            for role in ["admin", "mini"]
        }
    delivered = []
    assert dispatch(sessions, now, delivered.append, role="admin") == 1
    assert delivered == [ids["admin"]]
    assert claim(sessions, ids["mini"], now, settings=system["settings"], role="admin") is None
    with sessions() as db:
        assert db.get(Job, ids["mini"]).state == "queued"
        assert db.get(Job, ids["mini"]).attempts == 0
    assert dispatch(sessions, now, delivered.append, role="mini") == 1
    assert delivered[-1] == ids["mini"]
    assert (
        claim(sessions, ids["mini"], now, settings=system["settings"], role="mini")["attempt"] == 1
    )


def test_expired_lease_fences_late_worker_and_recovery_is_idempotent(system):
    claim, dispatch, enqueue, finish, fail, Job = api()
    sessions, now = system["sessions"], system["time"][0].replace(tzinfo=None)
    with sessions.begin() as db:
        job_id = enqueue(
            db,
            "media.decode",
            "admin",
            "actor",
            {"media_id": "one"},
            now,
            settings=system["settings"],
        ).id
    first = claim(sessions, job_id, now, settings=system["settings"])
    assert first and first["attempt"] == 1
    assert claim(sessions, job_id, now, settings=system["settings"]) is None
    later = now + timedelta(minutes=6)
    second = claim(sessions, job_id, later, settings=system["settings"])
    assert second and second["attempt"] == 2
    assert not finish(sessions, job_id, first["lease"], now, {"obsolete": True})
    assert finish(sessions, job_id, second["lease"], later, {"media_id": "one"})
    assert claim(sessions, job_id, later, settings=system["settings"]) is None
    with sessions() as db:
        assert db.get(Job, job_id).result == {"media_id": "one"}


def test_only_two_temporary_retries_and_never_persist_provider_exception(system):
    claim, dispatch, enqueue, finish, fail, Job = api()
    sessions, now = system["sessions"], system["time"][0].replace(tzinfo=None)
    with sessions.begin() as db:
        job_id = enqueue(
            db,
            "tts.synthesize",
            "admin",
            "actor",
            {"cache_key": "one"},
            now,
            settings=system["settings"],
        ).id
    for attempt in range(1, 4):
        current = now + timedelta(minutes=attempt)
        lease = claim(sessions, job_id, current, settings=system["settings"])
        assert lease and lease["attempt"] == attempt
        assert fail(sessions, job_id, lease["lease"], current, "provider_temporary", temporary=True)
    assert claim(sessions, job_id, now + timedelta(hours=1), settings=system["settings"]) is None
    with sessions() as db:
        job = db.get(Job, job_id)
        assert job.state == "failed" and job.error_code == "provider_temporary"
        assert job.attempts == 3


def test_terminal_receipt_and_side_effects_rollback_together(system):
    claim, dispatch, enqueue, finish, fail, Job = api()
    sessions, now = system["sessions"], system["time"][0].replace(tzinfo=None)
    with sessions.begin() as db:
        job_id = enqueue(
            db,
            "media.decode",
            "admin",
            "actor",
            {"media_id": "one"},
            now,
            settings=system["settings"],
        ).id
    lease = claim(sessions, job_id, now, settings=system["settings"])

    def broken(db, row):
        from juya_api.content_models import SettingCounter

        db.add(SettingCounter(name="must-rollback", value=1))
        db.flush()
        raise RuntimeError("commit side effect failed")

    with pytest.raises(RuntimeError):
        finish(sessions, job_id, lease["lease"], now, {}, apply=broken)
    with sessions() as db:
        from juya_api.content_models import SettingCounter

        assert db.get(SettingCounter, "must-rollback") is None
        assert db.get(Job, job_id).state == "running"


@pytest.mark.mysql
def test_real_mysql_only_one_worker_claims_a_delivered_job(system):
    if system["engine"].dialect.name != "mysql":
        pytest.skip("Real MySQL row locking")
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    claim, dispatch, enqueue, finish, fail, Job = api()
    now = system["admin"].app.state.clock()
    with system["sessions"].begin() as db:
        job_id = enqueue(
            db,
            "media.decode",
            "admin",
            "actor",
            {"media_id": "one"},
            now,
            settings=system["settings"],
        ).id
    barrier = Barrier(4)

    def attempt(_):
        barrier.wait()
        return claim(system["sessions"], job_id, now, settings=system["settings"])

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(attempt, range(4)))
    assert sum(value is not None for value in results) == 1
