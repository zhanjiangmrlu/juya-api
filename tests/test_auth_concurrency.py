import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

pytestmark = [
    pytest.mark.mysql,
    pytest.mark.skipif(
        not os.getenv("JUYA_TEST_DATABASE_URL"),
        reason="Real MySQL is required for concurrent identity constraints",
    ),
]


def test_same_login_attempt_is_redeemed_once_under_concurrent_requests(system):
    from juya_api.models import User

    barrier = Barrier(4)

    def attempt(_):
        with TestClient(system["mini"].app, base_url="https://testserver") as client:
            barrier.wait()
            return client.post(
                "/api/mini/v1/auth/wechat",
                headers={
                    "Idempotency-Key": "concurrent-one-attempt-0001",
                },
                json={"code": "alice:concurrent", "consent": True, "consent_version": "2026-10-17"},
            )

    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(attempt, range(4)))
    assert [r.status_code for r in responses] == [200, 200, 200, 200]
    assert len({r.json()["access_token"] for r in responses}) == 1
    assert system["wechat"].calls == 1
    with system["sessions"]() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1


def test_distinct_login_codes_for_the_same_wechat_identity_create_one_user(system):
    from juya_api.models import User

    barrier = Barrier(4)

    def attempt(index):
        with TestClient(system["mini"].app, base_url="https://testserver") as client:
            barrier.wait()
            return client.post(
                "/api/mini/v1/auth/wechat",
                headers={
                    "Idempotency-Key": f"concurrent-separate-attempt-{index}",
                },
                json={"code": f"alice:{index}", "consent": True, "consent_version": "2026-10-17"},
            )

    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(attempt, range(4)))
    assert [r.status_code for r in responses] == [200, 200, 200, 200]
    assert len({r.json()["user"]["id"] for r in responses}) == 1
    with system["sessions"]() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1
