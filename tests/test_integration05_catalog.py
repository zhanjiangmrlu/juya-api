"""Integration05 catalog writes and direct free-count policy use real HTTP/SQL."""

import pytest

from juya_api.listening_models import ListeningTopic
from tests.content_helpers import key
from tests.test_listening import A, article, post


def catalog_topic(admin, *, name="午间", name_en="A short break"):
    category = post(admin, A + "/categories", {"name": "日常"})
    return category, post(
        admin,
        A + "/topics",
        {"name": name, "name_en": name_en, "category_id": category["id"]},
    )


def test_topic_requires_english_but_allows_empty_chinese_and_reads_legacy(admin, system):
    category, topic = catalog_topic(admin, name="")
    assert topic["name"] == "" and topic["name_en"] == "A short break"
    for english in [None, "", "   "]:
        response = admin.post(
            A + "/topics",
            headers=key(),
            json={"name": "旧名称", "name_en": english, "category_id": category["id"]},
        )
        assert response.status_code == 422
    with system["sessions"].begin() as db:
        row = db.get(ListeningTopic, topic["id"])
        row.name, row.name_en = "历史中文主题", ""
    legacy = admin.get(A + "/topics").json()["items"][0]
    assert legacy["name"] == "历史中文主题" and legacy["name_en"] == ""


def test_empty_catalog_delete_checks_revision_and_replays_receipt(admin):
    category, topic = catalog_topic(admin)
    stale = admin.post(A + f"/topics/{topic['id']}/delete", headers=key(), json={"revision": 99})
    assert stale.status_code == 409
    headers = key()
    path = A + f"/topics/{topic['id']}/delete"
    accepted = admin.post(path, headers=headers, json={"revision": topic["revision"]})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "success"
    assert (
        admin.post(path, headers=headers, json={"revision": topic["revision"]}).json()
        == accepted.json()
    )
    assert admin.get(A + "/topics").json()["items"] == []
    assert (
        post(admin, A + f"/categories/{category['id']}/delete", {"revision": category["revision"]})[
            "status"
        ]
        == "success"
    )


def test_catalog_batch_delete_preserves_referenced_and_deletes_only_empty(admin):
    category, topic = catalog_topic(admin)
    empty = post(admin, A + "/categories", {"name": "空分类"})
    result = post(
        admin,
        A + "/categories/batch-delete",
        {"items": [{"id": r["id"], "revision": r["revision"]} for r in [category, empty]]},
    )["items"]
    assert result[0]["status"] == "failed"
    assert result[0]["references"]["topics"] == 1
    assert result[1]["status"] == "success"
    assert admin.get(A + "/categories").json()["items"][0]["id"] == category["id"]
    assert admin.get(A + "/topics").json()["items"][0]["id"] == topic["id"]


def test_deleted_article_is_a_reported_historical_catalog_reference(admin):
    _, topic = catalog_topic(admin)
    row = article(admin, topic["id"])
    post(admin, A + f"/articles/{row['id']}/delete", {"revision": row["revision"]})
    response = admin.post(
        A + f"/topics/{topic['id']}/delete", headers=key(), json={"revision": topic["revision"]}
    )
    assert response.status_code == 409
    assert response.json()["error"]["details"]["references"]["deleted_articles"] == 1


def test_free_count_saves_directly_with_version_and_idempotency(admin):
    current = admin.get(A + "/free-policy").json()
    headers = key()
    body = {"free_count": 0, "revision": current["revision"]}
    response = admin.put(A + "/free-policy", headers=headers, json=body)
    assert response.status_code == 200, response.text
    assert response.json()["configured"] is True
    assert response.json()["free_count"] == 0
    assert admin.put(A + "/free-policy", headers=headers, json=body).json() == response.json()
    assert admin.put(A + "/free-policy", headers=key(), json=body).status_code == 409


@pytest.mark.parametrize("count", [None, -1, 1.5, True, "2"])
def test_direct_free_count_rejects_non_integer_values(admin, count):
    current = admin.get(A + "/free-policy").json()
    response = admin.put(
        A + "/free-policy",
        headers=key(),
        json={"free_count": count, "revision": current["revision"]},
    )
    assert response.status_code == 422
