"""Approved acceptance behavior, using isolated persisted facts and real jobs."""

from datetime import timedelta

import pytest

from .content_helpers import draft, key, process_jobs, publish


def test_new_publications_top_manual_order_without_reordering_existing_queue(admin, mini, system):
    one = publish(admin, draft(admin))
    two = publish(admin, draft(admin, one["content"]))
    three = publish(admin, draft(admin, one["content"]))

    def ids():
        return [value["id"] for value in mini.get("/api/mini/v1/cards").json()["items"]]

    assert ids() == [three["id"], two["id"], one["id"]]
    current = admin.get("/api/admin/v1/catalog-order").json()
    manual = [two["id"], one["id"], three["id"]]
    ordered = admin.put(
        "/api/admin/v1/catalog-order",
        headers=key(),
        json={"version": current["version"], "card_ids": manual},
    )
    assert ordered.status_code == 200, ordered.text
    queue = mini.post(
        "/api/mini/v1/learning-queues",
        headers=key(),
        json={"source": "learning", "card_id": two["id"]},
    ).json()
    system["time"][0] += timedelta(minutes=1)
    saved = admin.put(
        f"/api/admin/v1/cards/{three['id']}",
        headers=key(),
        json={
            "revision": three["draft_revision"],
            "content": {**three["content"], "name": "新版本"},
        },
    ).json()
    publish(admin, saved)
    assert ids() == [three["id"], two["id"], one["id"]]
    # Even a new key cannot move an unchanged live publication again.
    publish(admin, two)
    assert ids() == [three["id"], two["id"], one["id"]]
    offline = admin.post(
        f"/api/admin/v1/cards/{one['id']}/offline",
        headers=key(),
        json={"revision": one["draft_revision"]},
    ).json()
    publish(admin, offline)
    assert ids() == [one["id"], three["id"], two["id"]]
    frozen = mini.get(f"/api/mini/v1/learning-queues/{queue['id']}").json()
    assert [value["card_id"] for value in frozen["items"]] == manual


def test_offline_new_preview_batch_real_job_restores_only_unlearned_list(admin, mini):
    one = publish(admin, draft(admin))
    two = publish(admin, draft(admin, one["content"]))
    completed = mini.post(
        f"/api/mini/v1/cards/{two['id']}/complete",
        headers=key(),
        json={"version_id": two["current_version_id"]},
    )
    assert completed.status_code == 200
    items = []
    for card in (one, two):
        offline = admin.post(
            f"/api/admin/v1/cards/{card['id']}/offline",
            headers=key(),
            json={"revision": card["draft_revision"]},
        ).json()
        preview = admin.post(
            f"/api/admin/v1/cards/{card['id']}/preview",
            headers=key(),
            json={"revision": offline["draft_revision"]},
        ).json()
        items.append(
            {
                "card_id": card["id"],
                "revision": offline["draft_revision"],
                "preview_id": preview["preview_id"],
            }
        )
    accepted = admin.post(
        "/api/admin/v1/publication-batches",
        headers=key(),
        json={"confirmed": True, "items": items},
    )
    assert accepted.status_code == 201, accepted.text
    assert all(item["state"] == "queued" for item in accepted.json()["items"])
    assert mini.get("/api/mini/v1/cards").json()["published_total"] == 0
    process_jobs(admin)
    result = admin.get(f"/api/admin/v1/publication-batches/{accepted.json()['id']}").json()
    assert all(item["state"] == "succeeded" for item in result["items"])
    listed = mini.get("/api/mini/v1/cards").json()
    assert listed["published_total"] == 2
    assert [item["id"] for item in listed["items"]] == [one["id"]]
    assert mini.get(f"/api/mini/v1/cards/{two['id']}").json()["state"]["completed"]


@pytest.mark.parametrize("source", ["records", "day"])
def test_deleted_records_filtered_before_pagination_counts_and_new_queue(
    admin, mini, system, source
):
    one = publish(admin, draft(admin))
    cards = [one] + [publish(admin, draft(admin, one["content"])) for _ in range(2)]
    for card in cards:
        system["time"][0] += timedelta(seconds=1)
        result = mini.post(
            f"/api/mini/v1/cards/{card['id']}/complete",
            headers=key(),
            json={"version_id": card["current_version_id"]},
        ).json()
    day = result["date"]
    before = mini.get("/api/mini/v1/me/statistics").json()
    # Most recent completion disappears, the remaining page must still be full.
    deleted = cards[2]
    response = admin.request(
        "DELETE",
        f"/api/admin/v1/cards/{deleted['id']}",
        headers=key(),
        json={"revision": deleted["draft_revision"]},
    )
    assert response.status_code == 200
    offline = admin.post(
        f"/api/admin/v1/cards/{cards[1]['id']}/offline",
        headers=key(),
        json={"revision": cards[1]["draft_revision"]},
    )
    assert offline.status_code == 200
    records = mini.get("/api/mini/v1/me/learning-records?limit=1").json()
    assert records["total"] == 2
    assert records["items"][0]["id"] == cards[1]["id"]
    assert records["items"][0]["unavailable_reason"] == "offline"
    assert (
        mini.get("/api/mini/v1/me/learning-records?limit=1&page=2").json()["items"][0]["id"]
        == one["id"]
    )
    detail = mini.get(f"/api/mini/v1/me/checkins/{day}").json()
    assert detail["total"] == 2
    assert {item["id"] for item in detail["items"]} == {one["id"], cards[1]["id"]}
    assert mini.get("/api/mini/v1/me/checkins").json()["items"][0]["card_count"] == 2
    assert mini.get("/api/mini/v1/me/statistics").json() == before
    body = {"source": source, "card_id": one["id"]}
    if source == "day":
        body["day"] = day
    # Put the live card first so the new queue must include all remaining records.
    with system["sessions"].begin() as db:
        from sqlalchemy import update

        from juya_api.learning_models import Completion, DailyLearning

        db.execute(
            update(Completion)
            .where(Completion.card_id == one["id"])
            .values(last_completed_at=system["time"][0] + timedelta(seconds=1))
        )
        db.execute(
            update(DailyLearning)
            .where(DailyLearning.card_id == one["id"])
            .values(accepted_at=system["time"][0] + timedelta(seconds=1))
        )
    queue = mini.post("/api/mini/v1/learning-queues", headers=key(), json=body)
    assert queue.status_code == 201, queue.text
    assert queue.json()["total"] == 2
    values = mini.get(f"/api/mini/v1/learning-queues/{queue.json()['id']}").json()["items"]
    assert {item["card_id"] for item in values} == {one["id"], cards[1]["id"]}
