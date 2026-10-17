"""MySQL must preserve subsecond acceptance times across task and Beijing-day boundaries."""

from datetime import UTC, datetime

from sqlalchemy import select


def test_job_is_immediately_dispatchable_at_fractional_second(system):
    from juya_api.job_models import Job
    from juya_api.jobs import dispatch, enqueue

    now = datetime(2026, 10, 17, 15, 59, 59, 999999)
    sessions = system["sessions"]
    with sessions.begin() as db:
        row = enqueue(db, "media.decode", "admin", "actor", {}, now, settings=system["settings"])
        job_id = row.id
    with sessions() as db:
        assert db.get(Job, job_id).available_at == now
    delivered = []
    assert dispatch(sessions, now, delivered.append, role="admin") == 1
    assert delivered == [job_id]


def test_registration_does_not_round_into_the_next_beijing_day(system):
    from juya_api.models import User

    now = datetime(2026, 10, 17, 15, 59, 59, 999999, tzinfo=UTC)
    system["time"][0] = now
    response = system["mini"].post(
        "/api/mini/v1/auth/wechat",
        json={
            "code": "fractional:first",
            "consent_version": "2026-10-17",
            "consent": True,
        },
        headers={"Idempotency-Key": "fractional-login-operation-001"},
    )
    assert response.status_code == 200
    with system["sessions"]() as db:
        user = db.scalar(select(User))
        assert user.registered_at == now.replace(tzinfo=None)
