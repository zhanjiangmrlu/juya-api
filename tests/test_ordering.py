from datetime import timedelta

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


def test_admin_list_uses_publication_time_and_ignores_later_draft_edits(admin, system):
    """发布顺序优先于创建顺序和手动排序，保存草稿不会将旧发布置顶"""
    one = draft(admin)
    system["time"][0] += timedelta(minutes=1)
    two = draft(admin, one["content"])
    system["time"][0] += timedelta(minutes=1)
    three = draft(admin, one["content"])
    for card in (two, one, three):
        system["time"][0] += timedelta(minutes=1)
        publish(admin, card)

    expected = [three["id"], one["id"], two["id"]]
    for params in ({}, {"status": "published"}, {"search": "Ordering Coffee"}):
        response = admin.get("/api/admin/v1/cards", params=params)
        assert response.status_code == 200, response.text
        assert [row["id"] for row in response.json()["items"]] == expected

    system["time"][0] += timedelta(minutes=1)
    saved = admin.put(
        f"/api/admin/v1/cards/{two['id']}",
        headers=key(),
        json={"revision": 1, "content": dict(two["content"], name="修改后的咖啡店")},
    )
    assert saved.status_code == 200, saved.text
    assert [row["id"] for row in admin.get("/api/admin/v1/cards").json()["items"]] == expected
    system["time"][0] += timedelta(minutes=1)
    publish(admin, saved.json())
    assert [row["id"] for row in admin.get("/api/admin/v1/cards").json()["items"]] == [
        two["id"],
        three["id"],
        one["id"],
    ]


def test_admin_draft_list_orders_newest_first_before_pagination_and_anchor(admin, system):
    """未发布卡片按创建时间倒序，定位和分页使用相同顺序"""
    cards = []
    for _ in range(12):
        cards.append(draft(admin, {"name": "待发布"}))
        system["time"][0] += timedelta(minutes=1)
    expected = [card["id"] for card in reversed(cards)]
    first = admin.get("/api/admin/v1/cards?status=draft").json()
    second = admin.get("/api/admin/v1/cards?status=draft&page=2").json()
    assert [row["id"] for row in first["items"]] == expected[:10]
    assert [row["id"] for row in second["items"]] == expected[10:]
    located = admin.get(
        "/api/admin/v1/cards", params={"status": "draft", "anchor_id": cards[0]["id"]}
    ).json()
    assert located["page"] == 2
    assert [row["id"] for row in located["items"]] == expected[10:]


def test_admin_published_list_has_stable_ties_and_matching_anchor_page(admin):
    """同一时刻批量发布时分页不重复或遗漏，定位仍落到卡片实际所在页"""
    first = draft(admin)
    cards = [first] + [draft(admin, first["content"]) for _ in range(11)]
    for card in cards:
        publish(admin, card)
    expected = sorted((card["id"] for card in cards), reverse=True)
    first_page = admin.get("/api/admin/v1/cards?status=published").json()
    second_page = admin.get("/api/admin/v1/cards?status=published&page=2").json()
    assert [row["id"] for row in first_page["items"]] == expected[:10]
    assert [row["id"] for row in second_page["items"]] == expected[10:]
    for card_id, page in ((expected[0], 1), (expected[-1], 2)):
        located = admin.get(
            "/api/admin/v1/cards", params={"status": "published", "anchor_id": card_id}
        ).json()
        assert located["page"] == page
        assert card_id in [row["id"] for row in located["items"]]
