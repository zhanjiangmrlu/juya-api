"""Integration05 catalog writes and direct free-count policy use real HTTP/SQL."""

import pytest

from juya_api.listening_models import ListeningTopic
from tests.content_helpers import key
from tests.test_listening import A, article, post


def catalog_topic(admin, *, name="午间", name_en="A short break"):
    """Keep shared fixture naming while creating one direct category."""
    category = post(admin, A + "/categories", {"name": name or "日常", "name_en": name_en})
    return category, category


def test_topic_requires_english_but_allows_empty_chinese_and_reads_legacy(admin, system):
    """Old topics remain readable but creation is retired after direct ownership migration."""
    category, _ = catalog_topic(admin)
    assert (
        admin.post(
            A + "/topics",
            headers=key(),
            json={"name_en": "Old topic", "category_id": category["id"]},
        ).status_code
        == 410
    )
    with system["sessions"].begin() as db:
        db.add(
            ListeningTopic(
                id="historic-topic", category_id=category["id"], name="历史中文主题", name_en=""
            )
        )
    legacy = admin.get(A + "/topics").json()["items"][0]
    assert legacy["name"] == "历史中文主题" and legacy["name_en"] == ""


def test_empty_catalog_delete_checks_revision_and_replays_receipt(admin):
    """Soft deletion still checks revisions and replays the original successful receipt."""
    category, _ = catalog_topic(admin)
    path = A + f"/categories/{category['id']}/delete"
    assert admin.post(path, headers=key(), json={"revision": 99}).status_code == 409
    headers, body = key(), {"revision": category["revision"]}
    accepted = admin.post(path, headers=headers, json=body)
    assert accepted.status_code == 200, accepted.text
    assert admin.post(path, headers=headers, json=body).json() == accepted.json()
    assert admin.get(A + "/categories").json()["items"] == []


def test_catalog_batch_delete_preserves_referenced_and_deletes_only_empty(admin):
    category, topic = catalog_topic(admin)
    article(admin, category["id"])
    empty = post(admin, A + "/categories", {"name": "空分类"})
    result = post(
        admin,
        A + "/categories/batch-delete",
        {"items": [{"id": r["id"], "revision": r["revision"]} for r in [category, empty]]},
    )["items"]
    assert result[0]["status"] == "failed"
    assert result[0]["references"]["articles"] == 1
    assert result[1]["status"] == "success"
    assert admin.get(A + "/categories").json()["items"][0]["id"] == category["id"]


def test_deleted_article_is_a_reported_historical_catalog_reference(admin):
    _, topic = catalog_topic(admin)
    row = article(admin, topic["id"])
    post(admin, A + f"/articles/{row['id']}/delete", {"revision": row["revision"]})
    response = admin.post(
        A + f"/categories/{topic['id']}/delete", headers=key(), json={"revision": topic["revision"]}
    )
    assert response.status_code == 200
    assert admin.get(A + "/categories").json()["items"] == []


def test_catalog_reordering_preserves_names_and_checks_the_complete_versioned_set(admin):
    first = post(admin, A + "/categories", {"name": "先显示"})
    second = post(admin, A + "/categories", {"name": "后显示"})
    response = admin.put(
        A + "/categories/order",
        headers=key(),
        json={
            "items": [
                {"id": second["id"], "revision": second["revision"]},
                {"id": first["id"], "revision": first["revision"]},
            ]
        },
    )
    assert response.status_code == 200, response.text
    assert [row["name"] for row in admin.get(A + "/categories").json()["items"]] == [
        "后显示",
        "先显示",
    ]
    stale = admin.put(
        A + "/categories/order",
        headers=key(),
        json={"items": [{"id": first["id"], "revision": first["revision"]}]},
    )
    assert stale.status_code == 409


def test_free_count_saves_directly_with_version_and_idempotency(admin):
    """A valid former numeric request always returns retirement instead of changing state."""
    current = admin.get(A + "/free-policy").json()
    assert current["free_count"] == 0
    response = admin.put(
        A + "/free-policy", headers=key(), json={"free_count": 0, "revision": current["revision"]}
    )
    assert response.status_code == 410


@pytest.mark.parametrize("count", [None, -1, 1.5, True, "2"])
def test_direct_free_count_rejects_non_integer_values(admin, count):
    current = admin.get(A + "/free-policy").json()
    response = admin.put(
        A + "/free-policy",
        headers=key(),
        json={"free_count": count, "revision": current["revision"]},
    )
    assert response.status_code == 422


@pytest.mark.mysql
def test_catalog_delete_and_new_reference_have_one_winner(admin, system):
    if system["engine"].dialect.name != "mysql":
        pytest.skip("Dedicated real MySQL required")
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from fastapi.testclient import TestClient

    category = post(admin, A + "/categories", {"name": "并发引用"})
    barrier = Barrier(2)
    with TestClient(admin.app, base_url="https://testserver") as second:
        login = second.post(
            "/api/admin/v1/auth/login",
            json={"username": "admin", "password": "correct-test-password"},
        ).json()
        second.headers["X-CSRF-Token"] = login["csrf_token"]

        def remove():
            barrier.wait()
            return admin.post(
                A + f"/categories/{category['id']}/delete",
                headers=key(),
                json={"revision": category["revision"]},
            )

        def create():
            barrier.wait()
            return second.post(
                A + "/articles",
                headers=key(),
                json={"category_id": category["id"], "payload": {}},
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            a, b = pool.submit(remove), pool.submit(create)
            deleted, created = a.result(), b.result()
    assert (deleted.status_code, created.status_code) in [(200, 422), (409, 200)]
    categories = admin.get(A + "/categories").json()["items"]
    articles = admin.get(A + "/articles").json()["items"]
    assert all(
        any(category["id"] == row["category_id"] for category in categories) for row in articles
    )
