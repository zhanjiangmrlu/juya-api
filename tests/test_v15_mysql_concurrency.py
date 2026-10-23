"""Real MySQL acceptance races; no test substitutes SQLite for row locks."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Barrier, Event

import pytest
from fastapi.testclient import TestClient

from .content_helpers import draft, key, publish
from .test_import_batch_deletion import delete
from .test_import_removal import make_batch

pytestmark = pytest.mark.mysql


def require_mysql(system):
    if system["engine"].dialect.name != "mysql":
        pytest.skip("Requires the verified private MySQL instance")


@pytest.mark.parametrize("action", ["publish", "offline", "delete", "order"])
def test_other_admin_catalog_mutation_waits_for_one_global_lock(admin, system, action):
    from juya_api.auth import passwords
    from juya_api.content_service import catalog_lock
    from juya_api.models import Administrator

    require_mysql(system)
    one = publish(admin, draft(admin))
    two = draft(admin, one["content"])
    with system["sessions"].begin() as db:
        db.add(
            Administrator(
                username="second", password_hash=passwords.hash("second-admin-test-password")
            )
        )
    with TestClient(admin.app, base_url="https://testserver") as second:
        login = second.post(
            "/api/admin/v1/auth/login",
            json={"username": "second", "password": "second-admin-test-password"},
        ).json()
        second.headers["X-CSRF-Token"] = login["csrf_token"]
        preview = second.post(
            f"/api/admin/v1/cards/{two['id']}/preview",
            headers=key(),
            json={"revision": two["draft_revision"]},
        ).json()
        order = second.get("/api/admin/v1/catalog-order").json()
        started = Event()

        def mutate():
            started.set()
            if action == "publish":
                return second.post(
                    f"/api/admin/v1/cards/{two['id']}/publish",
                    headers=key(),
                    json={"revision": two["draft_revision"], "preview_id": preview["preview_id"]},
                )
            if action == "order":
                return second.put(
                    "/api/admin/v1/catalog-order",
                    headers=key(),
                    json={"version": order["version"], "card_ids": [one["id"]]},
                )
            return second.request(
                "DELETE" if action == "delete" else "POST",
                f"/api/admin/v1/cards/{one['id']}" + ("" if action == "delete" else "/offline"),
                headers=key(),
                json={"revision": one["draft_revision"]},
            )

        with ThreadPoolExecutor(max_workers=1) as pool:
            with system["sessions"].begin() as db:
                catalog_lock(db)
                future = pool.submit(mutate)
                assert started.wait(timeout=5)
                with pytest.raises(TimeoutError):
                    future.result(timeout=0.5)
            response = future.result(timeout=20)
            assert response.status_code == 200, response.text


def test_concurrent_save_acceptance_and_batch_delete_have_one_winner(admin, system):
    require_mysql(system)
    batch = make_batch(admin, "并发保存删除")
    endpoint = f"/api/admin/v1/imports/{batch['id']}"
    confirmation = admin.get(endpoint + "/confirmation").json()
    barrier = Barrier(2)

    def save():
        barrier.wait(timeout=10)
        return admin.post(
            endpoint + "/save",
            headers=key(),
            json={"confirmed": True, "version": confirmation["version"]},
        )

    def remove():
        barrier.wait(timeout=10)
        return delete(admin, batch)

    with ThreadPoolExecutor(max_workers=2) as pool:
        saved, removed = pool.submit(save), pool.submit(remove)
        save_response, delete_response = saved.result(timeout=30), removed.result(timeout=30)
    assert (save_response.status_code, delete_response.status_code) in {(200, 409), (404, 200)}


def test_concurrent_delete_replays_one_durable_receipt(admin, system):
    from sqlalchemy import func, select

    from juya_api.models import Audit

    require_mysql(system)
    batch = make_batch(admin, "幂等删除")
    headers, barrier = key(), Barrier(2)

    def remove():
        barrier.wait(timeout=10)
        return delete(admin, batch, headers=headers)

    with ThreadPoolExecutor(max_workers=2) as pool:
        one, two = pool.submit(remove), pool.submit(remove)
        responses = [one.result(timeout=30), two.result(timeout=30)]
    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].json() == responses[1].json() == {"id": batch["id"], "deleted": True}
    with system["sessions"]() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Audit)
                .where(Audit.action == "import.delete", Audit.object_id == batch["id"])
            )
            == 1
        )


def test_action_worker_validates_live_snapshot_inside_catalog_lock(admin, system, monkeypatch):
    from sqlalchemy import select
    from sqlalchemy.exc import OperationalError

    from juya_api import admin_action_api
    from juya_api.content_models import SettingCounter

    from .content_helpers import process_jobs
    from .test_admin_operations import accept

    require_mysql(system)
    card = publish(admin, draft(admin))
    batch = accept(admin, "offline", [card]).json()
    original = admin_action_api.validate_snapshot

    def validate_with_concurrent_catalog_writer(db, selection):
        # A different administrator must be unable to change the live version
        # between checking the accepted snapshot and applying the lifecycle action.
        with system["sessions"].begin() as peer, pytest.raises(OperationalError):
            peer.scalar(
                select(SettingCounter)
                .where(SettingCounter.name == "catalog_revision")
                .with_for_update(nowait=True)
            )
        return original(db, selection)

    monkeypatch.setattr(
        admin_action_api, "validate_snapshot", validate_with_concurrent_catalog_writer
    )
    process_jobs(admin)
    result = admin.get(f"/api/admin/v1/card-action-batches/{batch['id']}").json()
    assert result["items"][0]["state"] == "succeeded", result
