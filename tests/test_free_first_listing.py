"""Free publications precede paid content before pagination, preserving manual ranks."""

from juya_api.content_models import Card
from juya_api.listening_models import ListeningArticle, ListeningCategory
from tests.content_helpers import key
from tests.test_integration06 import A, M, article, category, free, publish
from tests.test_revision15_learning import cards


def test_scene_free_first_is_global_and_keeps_manual_order_within_groups(admin, mini, system):
    rows = cards(admin, 4)
    with system["sessions"].begin() as db:
        for position, row in enumerate(rows):
            card = db.get(Card, row["id"])
            card.sort_order = position
            card.is_free = position in {1, 3}
    expected = [rows[i]["id"] for i in [1, 3, 0, 2]]
    actual = [
        mini.get("/api/mini/v1/cards", params={"limit": 1, "page": page}).json()["items"][0]["id"]
        for page in range(1, 5)
    ]
    assert actual == expected
    queued = mini.post(
        "/api/mini/v1/learning-queues",
        json={"source": "learning", "card_id": expected[0]},
        headers=key(),
    )
    assert queued.status_code == 201, queued.text
    assert queued.json()["total"] == len(expected)
    snapshot = mini.get(f"/api/mini/v1/learning-queues/{queued.json()['id']}").json()
    assert [row["card_id"] for row in snapshot["items"]] == expected
    first = mini.get("/api/mini/v1/cards", params={"limit": 1}).json()["items"][0]
    completed = mini.post(
        f"/api/mini/v1/cards/{first['id']}/complete",
        json={"version_id": first["version_id"]},
        headers=key(),
    )
    assert completed.status_code == 200, completed.text
    remaining = mini.get("/api/mini/v1/cards").json()
    assert remaining["total"] == 3
    assert [row["id"] for row in remaining["items"]] == expected[1:]


def test_listening_free_first_precedes_category_order_and_pagination(admin, mini, system):
    first, second = category(admin, "先分类"), category(admin, "后分类")
    rows = [publish(admin, article(admin, owner["id"])) for owner in [first, first, second, second]]
    with system["sessions"].begin() as db:
        for position, owner in enumerate([first, second]):
            db.get(ListeningCategory, owner["id"]).sort_order = position
        for position, row in enumerate(rows):
            db.get(ListeningArticle, row["id"]).category_order = position
    free(admin, rows[1])
    free(admin, rows[3])
    expected = [rows[i]["id"] for i in [1, 3, 0, 2]]
    actual = [
        mini.get(M + "/articles", params={"limit": 1, "page": page}).json()["items"][0]["id"]
        for page in range(1, 5)
    ]
    assert actual == expected
    scoped = mini.get(M + "/articles", params={"category_id": second["id"]}).json()["items"]
    assert [row["id"] for row in scoped] == [rows[3]["id"], rows[2]["id"]]
    free(admin, rows[3], False)
    changed = mini.get(M + "/articles").json()["items"]
    assert [row["id"] for row in changed] == [rows[i]["id"] for i in [1, 0, 2, 3]]
    assert mini.get(M + f"/articles/{rows[3]['id']}").status_code == 403
    manual = admin.get(A + "/order", params={"scope": "category", "category_id": second["id"]})
    assert manual.status_code == 200, manual.text
    assert manual.json()["article_ids"] == [rows[2]["id"], rows[3]["id"]]
