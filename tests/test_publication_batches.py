"""Only reviewed versions publish; one failure cannot undo another card."""

from .content_helpers import draft, key, process_jobs


def preview(admin, card):
    return admin.post(
        f"/api/admin/v1/cards/{card['id']}/preview",
        headers=key(),
        json={"revision": card["draft_revision"]},
    ).json()["preview_id"]


def test_partial_publish_recovers_durably_without_republishing_success(admin, mini):
    one, two = draft(admin), draft(admin)
    members = [
        {"card_id": card["id"], "revision": 1, "preview_id": preview(admin, card)}
        for card in [one, two]
    ]
    headers = key()
    created = admin.post(
        "/api/admin/v1/publication-batches",
        headers=headers,
        json={"confirmed": True, "items": members},
    )
    assert created.status_code == 201, created.text
    batch = created.json()
    assert (
        admin.post(
            "/api/admin/v1/publication-batches",
            headers=headers,
            json={"confirmed": True, "items": members},
        ).json()
        == batch
    )
    # Another saved candidate invalidates only its own preview.
    assert (
        admin.put(
            f"/api/admin/v1/cards/{two['id']}",
            headers=key(),
            json={"revision": 1, "content": dict(two["content"], name="changed")},
        ).status_code
        == 200
    )
    process_jobs(admin)
    result = admin.get(f"/api/admin/v1/publication-batches/{batch['id']}").json()
    assert [row["state"] for row in result["items"]] == ["succeeded", "failed"]
    assert result["items"][1]["error_code"] == "revision_changed"
    version = mini.get(f"/api/mini/v1/cards/{one['id']}").json()["version_id"]
    retry = admin.post(f"/api/admin/v1/publication-batches/{batch['id']}/retry", headers=key())
    assert retry.status_code == 200
    process_jobs(admin)
    assert mini.get(f"/api/mini/v1/cards/{one['id']}").json()["version_id"] == version
    assert mini.get("/api/mini/v1/cards").json()["total"] == 1


def test_batch_requires_explicit_confirmation_and_rejects_duplicate_members(admin):
    card = draft(admin)
    item = {"card_id": card["id"], "revision": 1, "preview_id": preview(admin, card)}
    assert (
        admin.post(
            "/api/admin/v1/publication-batches",
            headers=key(),
            json={"confirmed": False, "items": [item]},
        ).status_code
        == 422
    )
    assert (
        admin.post(
            "/api/admin/v1/publication-batches",
            headers=key(),
            json={"confirmed": True, "items": [item, item]},
        ).status_code
        == 422
    )
