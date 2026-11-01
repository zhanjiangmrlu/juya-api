"""Deterministic real-MySQL interleavings for the integration06 review fixes."""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

import pytest
from sqlalchemy import text

from tests import test_integration06_review as review
from tests.content_helpers import key
from tests.test_integration06 import A
from tests.test_integration06_review import (
    staged_words,
)

pytestmark = [
    pytest.mark.mysql,
    pytest.mark.skipif(
        not os.getenv("JUYA_TEST_DATABASE_URL"), reason="Dedicated real MySQL required"
    ),
]


def test_candidate_speech_and_edit_share_actor_catalog_batch_lock_order(admin, monkeypatch):
    """Force edit holding actor against speech reaching actor; neither may hold batch first."""
    import juya_api.transactions as transactions

    batch = staged_words(admin)
    candidate = batch["candidates"][0]
    base = A + f"/imports/{batch['id']}/candidates/{candidate['id']}"
    writer_ready, speech_at_actor = Event(), Event()
    counter_lock = Lock()
    calls = [0]
    original = transactions.actor_lock

    def interleave(db, actor, role):
        """Bound waits expose inverse row-lock order deterministically on a real MySQL server."""
        db.execute(text("SET SESSION innodb_lock_wait_timeout=3"))
        with counter_lock:
            calls[0] += 1
            index = calls[0]
        if index == 2:
            speech_at_actor.set()
        result = original(db, actor, role)
        if index == 1:
            writer_ready.set()
            assert speech_at_actor.wait(5), "Speech never reached actor lock"
        return result

    monkeypatch.setattr(transactions, "actor_lock", interleave)
    body = {
        "revision": batch["revision"],
        "category_id": candidate["category_id"],
        "payload": {**candidate["payload"], "title_zh": "并发核对更新"},
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        writer = pool.submit(admin.put, base, json=body, headers=key())
        assert writer_ready.wait(5), "Candidate edit never acquired actor lock"
        speech = pool.submit(
            admin.post,
            base + "/words/rest-one/pronunciation",
            json={"revision": batch["revision"]},
            headers=key(),
        )
        updated, generated = writer.result(timeout=12), speech.result(timeout=12)
    assert updated.status_code == 200, updated.text
    assert generated.status_code == 409, generated.text
    restored = admin.get(A + f"/imports/{batch['id']}").json()
    assert restored["revision"] == batch["revision"] + 1
    assert restored["candidates"][0]["payload"]["title_zh"] == "并发核对更新"


def test_multiple_pending_moves_keep_explicit_publication_order(admin, mini):
    """Run the actual category-move HTTP flow against MySQL row locks and persistent rows."""
    review.test_multiple_category_moves_allocate_order_at_publication_after_new_article(admin, mini)


def test_independent_admin_sessions_publish_pending_moves_without_tied_orders(admin, mini):
    """Two sessions of the sole administrator serialize real concurrent publication requests."""
    from threading import Barrier

    from fastapi.testclient import TestClient

    from tests.test_integration06 import M, article, category, publish
    from tests.test_integration06_review import move

    origin, target = category(admin), category(admin, "目标并发")
    existing = publish(admin, article(admin, target["id"]))
    rows = [publish(admin, article(admin, origin["id"])) for _ in range(2)]
    drafts = [move(admin, row, target) for row in rows]
    added = publish(admin, article(admin, target["id"]))
    barrier = Barrier(2)
    with TestClient(admin.app, base_url="https://testserver") as second:
        login = second.post(
            "/api/admin/v1/auth/login",
            json={"username": "admin", "password": "correct-test-password"},
        )
        assert login.status_code == 200, login.text
        second.headers["X-CSRF-Token"] = login.json()["csrf_token"]

        def publish_pending(client, row):
            """Release independent sessions together through the actor and catalog lock chain."""
            barrier.wait(timeout=5)
            return client.post(
                A + f"/articles/{row['id']}/publish",
                json={"revision": row["revision"]},
                headers=key(),
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            first_result = pool.submit(publish_pending, admin, drafts[0])
            second_result = pool.submit(publish_pending, second, drafts[1])
            results = [first_result.result(timeout=12), second_result.result(timeout=12)]
    assert [result.status_code for result in results] == [200, 200]
    published = [result.json() for result in results]
    assert sorted(row["category_order"] for row in published) == [3, 4]
    assert [row["version_id"] for row in published] == [row["version_id"] for row in rows]
    listing = mini.get(M + "/articles", params={"category_id": target["id"]}).json()["items"]
    assert [row["id"] for row in listing] == [existing["id"], added["id"]] + [
        row["id"] for row in sorted(published, key=lambda row: row["category_order"])
    ]
