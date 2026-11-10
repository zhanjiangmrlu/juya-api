"""Real MySQL serializes optional permission changes independently of grades."""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from juya_api.privacy_models import AnalyticsEventReceipt
from tests.test_privacy import DOCS, P, confirmation

pytestmark = [
    pytest.mark.mysql,
    pytest.mark.skipif(not os.getenv("JUYA_TEST_DATABASE_URL"), reason="Real local MySQL required"),
]


def test_competing_permission_revisions_have_one_winner(mini, system):
    mini.app.state.privacy_documents = DOCS
    assert (
        mini.post(
            P + "/me/agreements", json=confirmation(), headers={"Idempotency-Key": str(uuid4())}
        ).status_code
        == 200
    )
    barrier = Barrier(2)
    credential = mini.headers["Authorization"]

    def update(enabled):
        with TestClient(mini.app, base_url="https://testserver") as client:
            barrier.wait()
            return client.put(
                P + "/me/analytics-preference",
                json={"enabled": enabled, "scope_version": "v1", "expected_revision": 0},
                headers={"Authorization": credential, "Idempotency-Key": str(uuid4())},
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        values = list(pool.map(update, [True, False]))
    assert sorted(r.status_code for r in values) == [200, 409]
    assert mini.get(P + "/me/privacy").json()["analytics"]["revision"] == 1


def test_event_retry_concurrency_delivers_one_committed_receipt(mini, system):
    mini.app.state.privacy_documents = DOCS
    received = []
    mini.app.state.analytics_receiver = received.append
    mini.post(P + "/me/agreements", json=confirmation(), headers={"Idempotency-Key": str(uuid4())})
    mini.put(
        P + "/me/analytics-preference",
        json={"enabled": True, "scope_version": "v1", "expected_revision": 0},
        headers={"Idempotency-Key": str(uuid4())},
    )
    value = {
        "event_id": str(uuid4()),
        "event": "page_enter",
        "occurred_at": "2026-10-17T08:00:00Z",
        "consent_revision": 1,
        "properties": {"page_path": "pages/home/index"},
    }
    barrier = Barrier(4)
    credential = mini.headers["Authorization"]

    def submit(_):
        with TestClient(mini.app, base_url="https://testserver") as client:
            barrier.wait()
            return client.post(
                P + "/analytics/events", json=value, headers={"Authorization": credential}
            )

    with ThreadPoolExecutor(max_workers=4) as pool:
        values = list(pool.map(submit, range(4)))
    assert [v.status_code for v in values] == [200] * 4
    assert len(received) == 1
    assert received[0]["user_id"] != ""
    with system["sessions"]() as db:
        assert db.scalar(select(func.count()).select_from(AnalyticsEventReceipt)) == 1
