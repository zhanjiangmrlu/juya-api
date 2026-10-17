from .content_helpers import draft, key, publish


def test_only_complete_published_set_can_be_sorted_and_stale_window_conflicts(admin, mini):
    one, two = draft(admin), draft(admin)
    publish(admin, one)
    publish(admin, two)
    baseline = admin.get("/api/admin/v1/catalog-order")
    assert baseline.status_code == 200, baseline.text
    baseline = baseline.json()
    ids = [row["id"] for row in baseline["items"]]
    assert set(ids) == {one["id"], two["id"]}
    body = {"version": baseline["version"], "card_ids": list(reversed(ids))}
    headers = key()
    saved = admin.put("/api/admin/v1/catalog-order", headers=headers, json=body)
    assert saved.status_code == 200, saved.text
    assert (
        admin.put("/api/admin/v1/catalog-order", headers=headers, json=body).json() == saved.json()
    )
    assert [c["id"] for c in mini.get("/api/mini/v1/cards").json()["items"]] == list(reversed(ids))
    assert admin.put("/api/admin/v1/catalog-order", headers=key(), json=body).status_code == 409
    current = admin.get("/api/admin/v1/catalog-order").json()
    assert (
        admin.put(
            "/api/admin/v1/catalog-order",
            headers=key(),
            json={"version": current["version"], "card_ids": [one["id"]]},
        ).status_code
        == 422
    )
    # Membership changes invalidate a previously viewed complete set.
    third = draft(admin)
    publish(admin, third)
    assert (
        admin.put(
            "/api/admin/v1/catalog-order",
            headers=key(),
            json={"version": current["version"], "card_ids": [one["id"], two["id"]]},
        ).status_code
        == 409
    )


def test_catalog_order_uses_derived_thumbnails_instead_of_loading_all_originals(admin):
    card = draft(admin)
    publish(admin, card)
    image = admin.get(f"/api/admin/v1/media/{card['content']['image_id']}/status").json()
    listed = admin.get("/api/admin/v1/catalog-order").json()["items"][0]
    assert listed["thumbnail_id"] == image["thumbnail_id"]
    assert listed["thumbnail_id"] != listed["image_id"]
