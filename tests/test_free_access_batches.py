"""Cross-page free tasks freeze previews and commit each content receipt atomically."""

from sqlalchemy import func, select

from juya_api.access_models import AccessHistory
from juya_api.content_models import Card
from tests.content_helpers import content, draft, key, process_jobs, publish

P = "/api/admin/v1/free-access-batches"


def preview(admin, ids, enabled=False, kind="scene"):
    response = admin.post(
        P + "/preview", json={"content_type": kind, "ids": ids, "is_free": enabled}
    )
    assert response.status_code == 200, response.text
    return response.json()


def submit(admin, value, headers=None, path=P):
    response = admin.post(
        path,
        json={
            "preview_token": value["preview_token"],
            "items": [x for x in value["items"] if x["status"] == "pending"],
        },
        headers=headers or key(),
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_full_cross_page_selection_is_not_limited_by_dispatch_or_page_size(admin, system):
    payload = content(admin)
    cards = [publish(admin, draft(admin, {**payload, "name": f"场景{i}"})) for i in range(33)]
    unpublished = draft(admin, {**payload, "name": "草稿"})
    value = preview(
        admin, [x["id"] for x in cards] + [cards[0]["id"], unpublished["id"], "missing"]
    )
    assert value["total"] == 35 and value["applicable"] == 33 and value["skipped"] == 2
    assert {x["reason"] for x in value["items"] if x["status"] == "skipped"} == {
        "not_published",
        "content_missing",
    }
    headers = key()
    accepted = submit(admin, value, headers)
    assert submit(admin, value, headers)["id"] == accepted["id"]
    process_jobs(admin)
    result = admin.get(P + "/" + accepted["id"]).json()
    assert result["state"] == "succeeded"
    assert (result["succeeded"], result["skipped"], result["failed"], result["pending"]) == (
        33,
        2,
        0,
        0,
    )
    assert len(result["items"]) == 35
    with system["sessions"]() as db:
        assert db.scalar(select(func.count()).select_from(Card).where(Card.is_free.is_(True))) == 0
        audits = db.scalars(
            select(AccessHistory).where(AccessHistory.action == "scene.free.batch")
        ).all()
        assert len(audits) == 33
        assert all(x.after["batch_id"] == accepted["id"] for x in audits)
    process_jobs(admin)
    assert admin.get(P + "/" + accepted["id"]).json() == result


def test_changed_after_preview_fails_and_retry_is_failed_subset_only(admin, system):
    payload = content(admin)
    cards = [publish(admin, draft(admin, {**payload, "name": str(i)})) for i in range(2)]
    value = preview(admin, [x["id"] for x in cards])
    accepted = submit(admin, value)
    with system["sessions"].begin() as db:
        row = db.get(Card, cards[0]["id"])
        row.free_revision += 1
    process_jobs(admin)
    result = admin.get(P + "/" + accepted["id"]).json()
    assert (result["succeeded"], result["failed"]) == (1, 1)
    assert (
        next(x for x in result["items"] if x["status"] == "failed")["reason"]
        == "free_access_changed"
    )
    bad = preview(admin, [x["id"] for x in cards], True)
    response = admin.post(
        P + "/" + accepted["id"] + "/retry",
        json={
            "preview_token": bad["preview_token"],
            "items": [x for x in bad["items"] if x["status"] == "pending"],
        },
        headers=key(),
    )
    assert response.status_code == 409
    retry = submit(
        admin, preview(admin, [cards[0]["id"]]), path=P + "/" + accepted["id"] + "/retry"
    )
    process_jobs(admin)
    assert admin.get(P + "/" + retry["id"]).json()["succeeded"] == 1
    assert admin.get(P + "/" + accepted["id"]).json() == result


def test_preview_cannot_expand_or_promote_skips_and_zero_is_rejected(admin):
    card = publish(admin, draft(admin))
    value = preview(admin, [card["id"]], True)
    assert value["applicable"] == 0
    response = admin.post(
        P, json={"preview_token": value["preview_token"], "items": []}, headers=key()
    )
    assert response.status_code == 409
    value = preview(admin, [card["id"]])
    response = admin.post(
        P, json={"preview_token": value["preview_token"], "items": []}, headers=key()
    )
    assert response.status_code == 409


def test_listening_preview_uses_published_name_and_current_permissions(admin, system):
    from juya_api.listening_models import ListeningArticle, ListeningCategory
    from tests.test_listening import article
    from tests.test_listening import publish as publish_article

    published = publish_article(admin, article(admin, title="已发布标题"))
    with system["sessions"].begin() as db:
        row = db.get(ListeningArticle, published["id"])
        row.payload = {**row.payload, "title_zh": "未发布草稿标题"}
    value = preview(admin, [published["id"]], True, "listening")
    assert value["items"][0]["name"] == "已发布标题"
    accepted = submit(admin, value)
    with system["sessions"].begin() as db:
        row = db.get(ListeningArticle, published["id"])
        db.get(ListeningCategory, row.category_id).deleted_at = system["time"][0]
    process_jobs(admin)
    result = admin.get(P + "/" + accepted["id"]).json()
    assert result["failed"] == 1 and result["items"][0]["reason"] == "permission_denied"


def test_expired_lease_cannot_mutate_and_recovered_worker_never_replays_receipts(admin, system):
    from datetime import timedelta

    from juya_api.free_batches import run_batch
    from juya_api.jobs import claim
    from juya_api.worker import run_job

    card = publish(admin, draft(admin))
    accepted = submit(admin, preview(admin, [card["id"]]))
    now = admin.app.state.clock
    old = claim(system["sessions"], accepted["job_id"], now(), settings=system["settings"])
    system["time"][0] += timedelta(minutes=6)
    run_batch(system["settings"], system["sessions"], old, now)
    assert admin.get(P + "/" + accepted["id"]).json()["pending"] == 1
    run_job(system["settings"], system["sessions"], accepted["job_id"], clock=now)
    done = admin.get(P + "/" + accepted["id"]).json()
    assert done["succeeded"] == 1
    run_batch(system["settings"], system["sessions"], old, now)
    assert admin.get(P + "/" + accepted["id"]).json() == done


def test_concurrent_same_operation_acceptance_creates_one_task(admin, system):
    from concurrent.futures import ThreadPoolExecutor

    card = publish(admin, draft(admin))
    value, headers = preview(admin, [card["id"]]), key()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: submit(admin, value, headers), range(2)))
    assert results[0]["id"] == results[1]["id"]


def test_batch_close_revokes_existing_guest_ticket_and_preserves_personal_facts(
    admin, mini, system
):
    from tests.test_guest_content import P as MINI
    from tests.test_guest_content import personal_counts

    card = publish(admin, draft(admin))
    guest = system["mini"]
    ticket = guest.get(
        MINI + f"/cards/{card['id']}/media/{card['content']['audio_id']}/url",
        params={"version_id": card["current_version_id"]},
    ).json()
    assert guest.get(ticket["url"]).status_code == 200
    before = personal_counts(system)
    accepted = submit(admin, preview(admin, [card["id"]]))
    process_jobs(admin)
    assert admin.get(P + "/" + accepted["id"]).json()["succeeded"] == 1
    assert guest.get(ticket["url"]).status_code == 403
    assert guest.get(MINI + f"/cards/{card['id']}").status_code == 403
    assert personal_counts(system) == before


def test_independent_item_error_does_not_rollback_siblings_or_leave_pending(admin, monkeypatch):
    from juya_api import free_batches
    from juya_api.errors import DomainError

    payload = content(admin)
    cards = [publish(admin, draft(admin, {**payload, "name": str(i)})) for i in range(2)]
    accepted = submit(admin, preview(admin, [x["id"] for x in cards]))
    original = free_batches.inspect_item

    def fail_one(db, kind, content_id, target, *, lock=False):
        if lock and content_id == cards[0]["id"]:
            raise DomainError(403, "permission_denied", "管理员无操作权限")
        return original(db, kind, content_id, target, lock=lock)

    monkeypatch.setattr(free_batches, "inspect_item", fail_one)
    process_jobs(admin)
    result = admin.get(P + "/" + accepted["id"]).json()
    assert (result["succeeded"], result["failed"], result["pending"]) == (1, 1, 0)


def test_exhausted_worker_receipt_has_no_unclassified_pending_items(admin, system):
    from datetime import timedelta

    from juya_api.jobs import claim

    card = publish(admin, draft(admin))
    accepted = submit(admin, preview(admin, [card["id"]]))
    for _ in range(4):
        claim(
            system["sessions"],
            accepted["job_id"],
            admin.app.state.clock(),
            settings=system["settings"],
        )
        system["time"][0] += timedelta(minutes=6)
    result = admin.get(P + "/" + accepted["id"]).json()
    assert result["state"] == "failed"
    assert result["pending"] == 0 and result["failed"] == 1
