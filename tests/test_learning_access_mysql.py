"""Real MySQL serialization of renewal and revoke/completion transactions."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from .content_helpers import key
from .test_learning_access import change, configure, user_id
from .test_revision15_learning import cards


@pytest.mark.mysql
def test_concurrent_confirmations_extend_one_month_only(system, admin, mini):
    if system["engine"].dialect.name != "mysql":
        pytest.skip("Dedicated real MySQL required")
    uid = user_id(mini)
    change(admin, uid, "grant")
    path = f"/api/admin/v1/users/{uid}/learning-authorization"
    token = admin.post(path + "/preview", json={"action": "renew"}).json()["preview_token"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: admin.put(path, headers=key(), json={"preview_token": token}), range(2)
            )
        )
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert admin.get(path).json()["expires_on"] == "2026-12-17"
    assert admin.get(path + "/history").json()["total"] == 2


@pytest.mark.mysql
def test_revoke_and_complete_are_ordered_on_same_user_without_losing_statistics(
    system, admin, mini
):
    if system["engine"].dialect.name != "mysql":
        pytest.skip("Dedicated real MySQL required")
    card = cards(admin, 1)[0]
    uid = user_id(mini)
    change(admin, uid, "grant")
    configure(admin, 0)
    path = f"/api/admin/v1/users/{uid}/learning-authorization"
    token = admin.post(path + "/preview", json={"action": "revoke"}).json()["preview_token"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        revoke = pool.submit(admin.put, path, headers=key(), json={"preview_token": token})
        complete = pool.submit(
            mini.post,
            f"/api/mini/v1/cards/{card['id']}/complete",
            headers=key(),
            json={"version_id": card["current_version_id"]},
        )
        revoke_result, complete_result = revoke.result(), complete.result()
    assert revoke_result.status_code == 200
    assert complete_result.status_code in (200, 403)
    assert mini.get("/api/mini/v1/me/statistics").json()["completed_cards"] == (
        1 if complete_result.status_code == 200 else 0
    )
    assert admin.get(path).json()["status"] == "none"
