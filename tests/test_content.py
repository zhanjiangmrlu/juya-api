from .content_helpers import content, draft, key, publish


def test_incomplete_draft_is_saved_but_cannot_be_published(admin, mini):
    response = admin.post(
        "/api/admin/v1/cards", headers=key(), json={"content": {"name": "待补充"}}
    )
    assert response.status_code == 201
    card = response.json()
    assert card["issues"]
    assert mini.get("/api/mini/v1/cards").json()["total"] == 0
    assert (
        admin.post(
            f"/api/admin/v1/cards/{card['id']}/preview", headers=key(), json={"revision": 1}
        ).status_code
        == 422
    )


def test_publish_exposes_one_complete_snapshot_with_unique_highlight(admin, mini):
    card = draft(admin)
    assert card["content"]["vocabulary"][0]["source"]["quote"] == "coffee"
    published = publish(admin, card)
    listing = mini.get("/api/mini/v1/cards").json()
    assert listing["total"] == 1
    assert listing["items"][0]["id"] == card["id"]
    detail = mini.get(f"/api/mini/v1/cards/{card['id']}").json()
    assert detail["version_id"] == published["current_version_id"]
    assert detail["content"]["name"] == "在咖啡店点单"
    assert detail["content"]["chunks"] == []


def test_editing_and_failed_publish_leave_current_snapshot_unchanged(admin, mini):
    card = draft(admin)
    original = publish(admin, card)
    new = dict(card["content"], name="改名后的场景")
    saved = admin.put(
        f"/api/admin/v1/cards/{card['id']}", headers=key(), json={"revision": 1, "content": new}
    )
    assert saved.status_code == 200
    assert mini.get(f"/api/mini/v1/cards/{card['id']}").json()["content"]["name"] == "在咖啡店点单"
    updated = publish(admin, saved.json())
    assert updated["current_version_id"] != original["current_version_id"]
    stale = mini.get(f"/api/mini/v1/cards/{card['id']}?version_id={original['current_version_id']}")
    assert stale.status_code == 409


def test_stale_save_and_preview_cannot_overwrite_new_content(admin):
    card = draft(admin)
    preview = admin.post(
        f"/api/admin/v1/cards/{card['id']}/preview", headers=key(), json={"revision": 1}
    ).json()
    updated = admin.put(
        f"/api/admin/v1/cards/{card['id']}",
        headers=key(),
        json={"revision": 1, "content": dict(card["content"], name="新内容")},
    )
    assert updated.status_code == 200
    assert (
        admin.put(
            f"/api/admin/v1/cards/{card['id']}",
            headers=key(),
            json={"revision": 1, "content": card["content"]},
        ).status_code
        == 409
    )
    assert (
        admin.post(
            f"/api/admin/v1/cards/{card['id']}/publish",
            headers=key(),
            json={"revision": 1, "preview_id": preview["preview_id"]},
        ).status_code
        == 409
    )


def test_word_candidates_do_not_match_substrings_and_manual_ranges_must_be_valid(admin):
    payload = content(admin)
    payload["dialogue"][0]["english"] = "The buyer bought a book."
    payload["vocabulary"] = [{"english": "buy", "meaning": "买"}]
    card = draft(admin, payload)
    assert any(i["code"] == "source_required" for i in card["issues"])
    payload["vocabulary"][0]["source"] = {
        "line_id": "line-1",
        "start": 10,
        "end": 16,
        "quote": "bought",
    }
    updated = admin.put(
        f"/api/admin/v1/cards/{card['id']}", headers=key(), json={"revision": 1, "content": payload}
    ).json()
    assert updated["issues"] == []


def test_repeated_operation_returns_same_card_and_changed_body_conflicts(admin):
    headers = key()
    first = admin.post(
        "/api/admin/v1/cards", headers=headers, json={"content": {"name": "同一操作"}}
    )
    second = admin.post(
        "/api/admin/v1/cards", headers=headers, json={"content": {"name": "同一操作"}}
    )
    assert first.json() == second.json()
    assert (
        admin.post(
            "/api/admin/v1/cards", headers=headers, json={"content": {"name": "另一操作"}}
        ).status_code
        == 409
    )


def test_offline_and_delete_block_new_access_and_stale_revival(admin, mini):
    card = draft(admin)
    publish(admin, card)
    assert (
        admin.post(
            f"/api/admin/v1/cards/{card['id']}/offline", headers=key(), json={"revision": 1}
        ).status_code
        == 200
    )
    assert mini.get(f"/api/mini/v1/cards/{card['id']}").status_code == 410
    assert mini.get("/api/mini/v1/cards").json()["total"] == 0
    publish(admin, card)
    assert (
        admin.request(
            "DELETE", f"/api/admin/v1/cards/{card['id']}", headers=key(), json={"revision": 1}
        ).status_code
        == 200
    )
    assert (
        admin.post(
            f"/api/admin/v1/cards/{card['id']}/preview", headers=key(), json={"revision": 1}
        ).status_code
        == 410
    )


def test_learner_cannot_create_or_edit_cards(mini):
    assert mini.post("/api/admin/v1/cards", json={"content": {}}).status_code == 404


def test_operation_replay_does_not_regenerate_missing_dialogue_or_word_ids(admin):
    payload = content(admin)
    del payload["dialogue"][0]["id"]
    del payload["vocabulary"][0]["id"]
    headers = key()
    first = admin.post("/api/admin/v1/cards", headers=headers, json={"content": payload})
    second = admin.post("/api/admin/v1/cards", headers=headers, json={"content": payload})
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
