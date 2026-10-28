"""Real MySQL row locks and uniqueness, using the isolated juya_verify database only."""

import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from tests.content_helpers import key
from tests.test_listening import A, M, article, policy, publish

pytestmark = [
    pytest.mark.mysql,
    pytest.mark.skipif(
        not os.getenv("JUYA_TEST_DATABASE_URL"),
        reason="Dedicated MySQL verification database required",
    ),
]


def test_concurrent_duplicate_completion_returns_one_durable_receipt(admin, mini, system):
    from juya_api.learning_models import Checkin
    from juya_api.listening_models import ListeningCompletion, ListeningDaily

    row = publish(admin, article(admin))
    policy(admin, 1)
    headers = key()

    def submit(_):
        return mini.post(
            M + f"/articles/{row['id']}/complete",
            headers=headers,
            json={"version_id": row["version_id"]},
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(submit, range(8)))
    assert [r.status_code for r in responses] == [200] * 8
    assert all(r.json() == responses[0].json() for r in responses)
    with system["sessions"]() as db:
        for model in [ListeningCompletion, ListeningDaily, Checkin]:
            assert db.scalar(select(func.count()).select_from(model)) == 1


def test_concurrent_distinct_articles_share_one_daily_checkin(admin, mini, system):
    from juya_api.learning_models import Checkin
    from juya_api.listening_models import ListeningCompletion, ListeningDaily

    rows = [publish(admin, article(admin)) for _ in range(2)]
    policy(admin, 2)

    def submit(index):
        row = rows[index % 2]
        return mini.post(
            M + f"/articles/{row['id']}/complete",
            headers=key(),
            json={"version_id": row["version_id"]},
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(submit, range(8)))
    assert [r.status_code for r in responses] == [200] * 8
    stats = mini.get(M + "/statistics").json()
    assert stats["completed_articles"] == stats["today_completed_articles"] == 2
    assert stats["total_checkin_days"] == 1
    with system["sessions"]() as db:
        assert db.scalar(select(func.count()).select_from(ListeningCompletion)) == 2
        assert db.scalar(select(func.count()).select_from(ListeningDaily)) == 2
        assert db.scalar(select(func.count()).select_from(Checkin)) == 1


def test_late_worker_result_cannot_replace_new_draft_input(admin, system):
    from juya_api.listening_models import ListeningJob
    from juya_api.listening_timeline import run_timeline_job
    from tests.test_listening_boundaries import recognized

    row = article(admin)
    old_job = row["timeline"]["job_id"]

    class Provider:
        def submit(self, audio):
            return "accepted"

        def poll(self, task_id):
            response = admin.put(
                A + f"/articles/{row['id']}",
                headers=key(),
                json={
                    "revision": row["revision"],
                    "topic_id": row["topic_id"],
                    "payload": {**row["payload"], "body_en": "A new saved body."},
                },
            )
            assert response.status_code == 200
            return recognized(row["payload"]["body_en"])

    run_timeline_job(system["settings"], system["sessions"], old_job, provider=Provider())
    current = admin.get(A + f"/articles/{row['id']}").json()
    assert current["timeline"]["input_hash"] != row["timeline"]["input_hash"]
    assert current["timeline"]["state"] == "pending"
    with system["sessions"]() as db:
        assert db.get(ListeningJob, old_job).state == "cancelled"
