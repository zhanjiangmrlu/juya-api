"""Review regressions for controlled speech locks, category order and publication images."""

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from tests.content_helpers import key, picture
from tests.test_integration06 import A, M, article, category, free, publish, vocabulary
from tests.test_listening_imports import assign, package, post, upload


def move(admin, row, owner):
    """Save a category-only draft without changing its immutable content."""
    response = admin.put(
        A + f"/articles/{row['id']}",
        json={"revision": row["revision"], "category_id": owner["id"], "payload": row["payload"]},
        headers=key(),
    )
    assert response.status_code == 200, response.text
    return response.json()


def illustrated(admin, row):
    """Attach a private image to an existing article draft."""
    medium = admin.post(
        A + f"/articles/{row['id']}/media?kind=image",
        headers=key(),
        files={"file": ("image.png", picture(), "image/png")},
    )
    assert medium.status_code == 200, medium.text
    response = admin.put(
        A + f"/articles/{row['id']}",
        json={
            "revision": row["revision"],
            "category_id": row["category_id"],
            "payload": {**row["payload"], "image_id": medium.json()["id"]},
        },
        headers=key(),
    )
    assert response.status_code == 200, response.text
    return response.json()


def staged_words(admin):
    """Stage controlled vocabulary in an owned review batch."""
    owner = category(admin)
    batch = upload(admin, post(admin, A + "/imports", {"mode": "zip"}), package())
    batch = assign(admin, batch, batch["candidates"][0]["id"], owner["id"])
    candidate = batch["candidates"][0]
    payload = {**candidate["payload"], "vocabulary": vocabulary()}
    # Staging speech resolves a saved word without requiring publication.
    result = admin.put(
        A + f"/imports/{batch['id']}/candidates/{candidate['id']}",
        json={"revision": batch["revision"], "category_id": owner["id"], "payload": payload},
        headers=key(),
    )
    assert result.status_code == 200, result.text
    return result.json()


def test_multiple_category_moves_allocate_order_at_publication_after_new_article(admin, mini):
    """Pending moves and intervening additions cannot share a final category position."""
    origin, target = category(admin), category(admin, "目标")
    existing = publish(admin, article(admin, target["id"]))
    first, second = [publish(admin, article(admin, origin["id"])) for _ in range(2)]
    first_draft, second_draft = move(admin, first, target), move(admin, second, target)
    new = publish(admin, article(admin, target["id"]))
    moved_first, moved_second = publish(admin, first_draft), publish(admin, second_draft)
    expected = [existing, new, moved_first, moved_second]
    assert [row["category_order"] for row in expected] == [1, 2, 3, 4]
    assert moved_first["version_id"] == first["version_id"]
    assert moved_second["version_id"] == second["version_id"]
    for row in expected:
        free(admin, row)
    page = mini.get(M + "/articles", params={"category_id": target["id"]}).json()
    assert [row["id"] for row in page["items"]] == [row["id"] for row in expected]
    assert mini.get(M + f"/articles/{new['id']}/next").json()["article"]["id"] == first["id"]


@pytest.mark.parametrize("draft_change", ["remove", "add_earlier"])
def test_category_thumbnail_uses_first_nonempty_published_thumbnail(admin, mini, draft_change):
    """Adding or removing an unpublished image cannot alter a category's learner image."""
    owner = category(admin)
    if draft_change == "add_earlier":
        earlier = publish(admin, article(admin, owner["id"]))
    carrier = publish(admin, illustrated(admin, article(admin, owner["id"])))
    expected = mini.get(M + f"/articles/{carrier['id']}/summary").json()["thumbnail_url"]
    assert expected
    assert mini.get(M + "/home").json()["categories"][0]["thumbnail_url"] == expected
    if draft_change == "remove":
        response = admin.put(
            A + f"/articles/{carrier['id']}",
            json={
                "revision": carrier["revision"],
                "category_id": owner["id"],
                "payload": {**carrier["payload"], "image_id": None},
            },
            headers=key(),
        )
        assert response.status_code == 200, response.text
    else:
        illustrated(admin, earlier)
    assert mini.get(M + "/home").json()["categories"][0]["thumbnail_url"] == expected


def test_import_speech_get_does_not_acquire_batch_write_lock(admin):
    """Speech polling must remain a read rather than take an import-row FOR UPDATE lock."""
    batch = staged_words(admin)
    candidate = batch["candidates"][0]
    locked = []

    def observe(execute_state):
        """Observe actual ORM SQL locking clauses, without replacing production operations."""
        statement = execute_state.statement
        if getattr(statement, "_for_update_arg", None) is not None and "listening_imports" in str(
            statement
        ):
            locked.append(str(statement))

    event.listen(Session, "do_orm_execute", observe)
    try:
        result = admin.get(
            A + f"/imports/{batch['id']}/candidates/{candidate['id']}/words/rest-one/pronunciation",
            params={"revision": batch["revision"]},
        )
        assert result.status_code == 200, result.text
    finally:
        event.remove(Session, "do_orm_execute", observe)
    assert locked == []
