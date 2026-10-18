"""Administration-only pagination and durable lifecycle actions preserve learning."""

from .content_helpers import content, draft, key, process_jobs, publish


def snapshot(card):
    return {
        "card_id": card["id"],
        "revision": card["draft_revision"],
        "status": card["status"],
        "version_id": card["current_version_id"],
    }


def accept(admin, action, cards, skipped=None, headers=None):
    return admin.post(
        "/api/admin/v1/card-action-batches",
        headers=headers or key(),
        json={
            "action": action,
            "confirmed": True,
            "items": [snapshot(c) for c in cards],
            "skipped": [snapshot(c) for c in (skipped or [])],
        },
    )


def test_admin_pagination_caps_clamps_and_searches_the_entire_set(admin):
    assert admin.get("/api/admin/v1/cards").json()["total_pages"] == 0
    for number in range(21):
        admin.post(
            "/api/admin/v1/cards", headers=key(), json={"content": {"name": f"卡片{number:02}"}}
        )
        if number in {0, 9, 10, 20}:
            value = admin.get("/api/admin/v1/cards?page=99").json()
            assert value["total"] == number + 1
            assert value["total_pages"] == (number + 10) // 10
            assert len(value["items"]) == number % 10 + 1
    first = admin.get("/api/admin/v1/cards?limit=1000").json()
    assert len(first["items"]) == 10 and first["limit"] == 10 and first["total_pages"] == 3
    last = admin.get("/api/admin/v1/cards?page=99").json()
    assert last["page"] == 3 and len(last["items"]) == 1
    assert not {c["id"] for c in first["items"]} & {c["id"] for c in last["items"]}
    located = admin.get("/api/admin/v1/cards?anchor_id=" + last["items"][0]["id"]).json()
    assert located["page"] == 3 and located["items"][0]["id"] == last["items"][0]["id"]
    found = admin.get("/api/admin/v1/cards?search=卡片20&page=99").json()
    assert (
        found["total"] == 1 and found["page"] == 1 and found["items"][0]["display_name"] == "卡片20"
    )
    empty = admin.get("/api/admin/v1/cards?search=不存在").json()
    assert empty["page"] == 1 and empty["total_pages"] == 0 and empty["items"] == []
    removed = admin.request(
        "DELETE",
        "/api/admin/v1/cards/" + last["items"][0]["id"],
        headers=key(),
        json={"revision": last["items"][0]["draft_revision"]},
    )
    assert removed.status_code == 200, removed.text
    after = admin.get("/api/admin/v1/cards?page=3").json()
    assert after["page"] == 2 and after["total_pages"] == 2 and after["total"] == 20


def test_display_image_stays_on_publication_while_candidate_changes(admin):
    original = draft(admin)
    live = publish(admin, original)
    replacement = content(admin)
    changed = admin.put(
        f"/api/admin/v1/cards/{live['id']}",
        headers=key(),
        json={"revision": live["draft_revision"], "content": replacement},
    ).json()
    assert changed["display_image_id"] == original["content"]["image_id"]
    assert changed["content"]["image_id"] != changed["display_image_id"]
    offline = admin.post(
        f"/api/admin/v1/cards/{live['id']}/offline",
        headers=key(),
        json={"revision": changed["draft_revision"]},
    ).json()
    assert offline["display_image_id"] == original["content"]["image_id"]


def test_mixed_offline_is_durable_and_replays_without_reexecuting(admin):
    live = publish(admin, draft(admin))
    pending = draft(admin)
    headers = key()
    created = accept(admin, "offline", [live], [pending], headers)
    assert created.status_code == 201, created.text
    batch = created.json()
    assert accept(admin, "offline", [live], [pending], headers).json() == batch
    process_jobs(admin)
    result = admin.get("/api/admin/v1/card-action-batches/" + batch["id"]).json()
    assert [i["state"] for i in result["items"]] == ["succeeded", "skipped"]
    assert admin.get("/api/admin/v1/cards/" + live["id"]).json()["status"] == "offline"
    job = result["items"][0]["job_id"]
    retry = admin.post(
        "/api/admin/v1/card-action-batches/" + batch["id"] + "/retry", headers=key()
    ).json()
    assert retry["items"][0]["job_id"] == job
    assert admin.get("/api/admin/v1/card-action-batches").json()[0]["id"] == batch["id"]


def test_only_stale_member_fails_and_requires_new_confirmation(admin):
    cards = [publish(admin, draft(admin)) for _ in range(2)]
    created = accept(admin, "delete", cards).json()
    changed = admin.put(
        "/api/admin/v1/cards/" + cards[1]["id"],
        headers=key(),
        json={
            "revision": cards[1]["draft_revision"],
            "content": dict(cards[1]["content"], name="新稿"),
        },
    )
    assert changed.status_code == 200
    process_jobs(admin)
    result = admin.get("/api/admin/v1/card-action-batches/" + created["id"]).json()
    assert [i["state"] for i in result["items"]] == ["succeeded", "failed"]
    assert result["items"][1]["needs_review"] is True
    retry = admin.post(
        "/api/admin/v1/card-action-batches/" + created["id"] + "/retry", headers=key()
    ).json()
    assert retry["items"][1]["job_id"] == result["items"][1]["job_id"]
    assert admin.get("/api/admin/v1/cards/" + cards[1]["id"]).status_code == 200


def test_batch_delete_keeps_completed_learning_and_updates_real_statistics(admin, mini):
    card = publish(admin, draft(admin))
    pending = draft(admin)
    offline = publish(admin, draft(admin))
    offline = admin.post(
        "/api/admin/v1/cards/" + offline["id"] + "/offline",
        headers=key(),
        json={"revision": offline["draft_revision"]},
    ).json()
    completed = mini.post(
        "/api/mini/v1/cards/" + card["id"] + "/complete",
        headers=key(),
        json={"version_id": card["current_version_id"]},
    )
    assert completed.status_code == 200, completed.text
    before = mini.get("/api/mini/v1/me/statistics").json()
    response = accept(admin, "delete", [card, pending, offline])
    assert response.status_code == 201
    process_jobs(admin)
    result = admin.get("/api/admin/v1/card-action-batches/" + response.json()["id"]).json()
    assert [item["state"] for item in result["items"]] == ["succeeded"] * 3
    assert admin.get("/api/admin/v1/cards/" + card["id"]).status_code == 410
    assert mini.get("/api/mini/v1/me/statistics").json() == before
    assert admin.get("/api/admin/v1/statistics").json()["published_card_count"] == 0


def test_retry_temporary_failure_keeps_success_and_original_scope(admin, system):
    from juya_api.job_models import Job

    cards = [draft(admin), draft(admin)]
    response = accept(admin, "delete", cards)
    assert response.status_code == 201
    batch = response.json()
    with system["sessions"].begin() as db:
        job = db.get(Job, batch["items"][1]["job_id"])
        job.state, job.error_code = "failed", "worker_interrupted"
    process_jobs(admin)
    result = admin.post(
        "/api/admin/v1/card-action-batches/" + batch["id"] + "/retry", headers=key()
    ).json()
    assert result["items"][0]["job_id"] == batch["items"][0]["job_id"]
    assert result["items"][1]["job_id"] != batch["items"][1]["job_id"]
    process_jobs(admin)
    assert admin.get("/api/admin/v1/cards").json()["total"] == 0


def test_batch_validates_role_duplicates_and_confirmation(admin, mini):
    card = draft(admin)
    assert mini.post("/api/admin/v1/card-action-batches", headers=key(), json={}).status_code == 404
    assert accept(admin, "delete", [card, card]).status_code == 422
    assert (
        admin.post(
            "/api/admin/v1/card-action-batches",
            headers=key(),
            json={"action": "delete", "confirmed": False, "items": [snapshot(card)]},
        ).status_code
        == 422
    )


def test_uploaded_audio_filename_survives_status_reload(admin):
    from .content_helpers import recording

    response = admin.post(
        "/api/admin/v1/media?kind=audio",
        headers=key(),
        files={"file": ("原始完整音频.wav", recording(), "audio/wav")},
    )
    assert response.status_code == 201
    media_id = response.json()["id"]
    process_jobs(admin)
    status = admin.get("/api/admin/v1/media/" + media_id + "/status").json()
    assert status["original_name"] == "原始完整音频.wav" and status["duration"] == 1


def test_sort_snapshot_expires_after_offline_and_republish_of_unchanged_content(admin):
    card = publish(admin, draft(admin))
    order = admin.get("/api/admin/v1/catalog-order").json()
    stopped = admin.post(
        "/api/admin/v1/cards/" + card["id"] + "/offline",
        headers=key(),
        json={"revision": card["draft_revision"]},
    ).json()
    publish(admin, stopped)
    response = admin.put(
        "/api/admin/v1/catalog-order",
        headers=key(),
        json={"version": order["version"], "card_ids": [card["id"]]},
    )
    assert response.status_code == 409
