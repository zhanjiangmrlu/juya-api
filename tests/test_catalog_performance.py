"""Catalog reads keep SQL work bounded as a page or category grows."""

import io
import random
from contextlib import contextmanager
from datetime import timedelta

import pytest
from PIL import Image
from sqlalchemy import event, select

from juya_api.listening_models import (
    ListeningArticle as Article,
)
from juya_api.listening_models import (
    ListeningCompletion as Completion,
)
from juya_api.listening_models import (
    ListeningDaily as Daily,
)
from juya_api.listening_models import (
    ListeningFavorite as Favorite,
)
from juya_api.listening_models import (
    ListeningVersion as Version,
)
from juya_api.models import User, identifier
from tests.content_helpers import content, draft, key
from tests.content_helpers import publish as publish_scene
from tests.test_listening import A, M, article, post, publish, topic


@contextmanager
def sql_reads(system):
    statements = []

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(system["engine"], "before_cursor_execute", capture)
    try:
        yield statements
    finally:
        event.remove(system["engine"], "before_cursor_execute", capture)


def listening_catalog(admin, system, count=12):
    owner = topic(admin)
    base = publish(admin, article(admin, owner["id"]))
    ids = [base["id"]]
    with system["sessions"].begin() as db:
        original = db.get(Article, base["id"])
        payload = db.get(Version, original.version_id).payload
        user_id = db.scalar(select(User.id))
        for number in range(count):
            if number:
                row = Article(
                    id=identifier(),
                    category_id=owner["id"],
                    status="published",
                    version_id=identifier(),
                    payload=payload,
                    is_free=number % 2 == 0,
                    global_order=number,
                    category_order=number,
                )
                db.add(row)
                db.flush()
                db.add(
                    Version(
                        id=row.version_id,
                        article_id=row.id,
                        payload=payload,
                        published_at=system["time"][0],
                    )
                )
                db.flush()
                ids.append(row.id)
            else:
                row = original
                row.is_free = True
            db.add(Favorite(user_id=user_id, article_id=row.id, created_at=system["time"][0]))
            db.add(
                Completion(
                    user_id=user_id,
                    article_id=row.id,
                    first_completed_at=system["time"][0],
                    last_completed_at=system["time"][0],
                    first_version_id=row.version_id,
                    last_version_id=row.version_id,
                )
            )
            if number % 2 == 0:
                from juya_api.learning_service import business_date

                db.add(
                    Daily(
                        user_id=user_id,
                        article_id=row.id,
                        version_id=row.version_id,
                        date=business_date(system["time"][0]),
                        accepted_at=system["time"][0],
                    )
                )
    return owner, ids


@pytest.mark.parametrize("collection", ["articles", "favorites", "records"])
def test_listening_page_sql_does_not_grow_per_article(admin, mini, system, collection):
    _, ids = listening_catalog(admin, system)
    with sql_reads(system) as single:
        response = mini.get(M + f"/{collection}?limit=1")
        assert response.status_code == 200, response.text
    with sql_reads(system) as full:
        response = mini.get(M + f"/{collection}?limit=12")
        assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) == 12 and {row["id"] for row in items} == set(ids)
    assert all(row["state"]["favorite"] and row["state"]["completed"] for row in items)
    assert sum(row["state"]["today_completed"] for row in items) == 6
    assert sum(row["access"]["can_learn"] for row in items) == 6
    assert len(full) <= len(single) + 2, (len(single), len(full))
    assert len(full) <= 15


def test_listening_home_sql_does_not_grow_per_article(admin, mini, system):
    with sql_reads(system) as empty:
        assert mini.get(M + "/home").status_code == 200
    owner, _ = listening_catalog(admin, system)
    with sql_reads(system) as populated:
        response = mini.get(M + "/home")
    assert response.status_code == 200, response.text
    category = response.json()["categories"][0]
    assert category["id"] == owner["id"]
    assert (
        category["total_articles"],
        category["completed_articles"],
        category["restricted_articles"],
    ) == (12, 12, 6)
    assert len(populated) <= len(empty) + 3, (len(empty), len(populated))
    assert len(populated) <= 24


def test_scene_page_sql_does_not_grow_per_card(admin, mini, system):
    payload = content(admin)
    for _ in range(10):
        publish_scene(admin, draft(admin, payload))
    with sql_reads(system) as single:
        assert mini.get("/api/mini/v1/cards?limit=1").status_code == 200
    with sql_reads(system) as full:
        response = mini.get("/api/mini/v1/cards?limit=10")
    assert response.status_code == 200, response.text
    assert len(response.json()["items"]) == 10
    assert all(item["access"]["can_learn"] for item in response.json()["items"])
    assert len(full) <= len(single) + 1, (len(single), len(full))


def test_listening_thumbnail_is_small_and_rechecks_scope_before_cached_range(
    admin, mini, system, monkeypatch
):
    from juya_api.storage import ObjectStorage

    row = article(admin)
    output = io.BytesIO()
    Image.frombytes("RGB", (1024, 1536), random.Random(17).randbytes(1024 * 1536 * 3)).save(
        output, "PNG"
    )
    original = output.getvalue()
    uploaded = admin.post(
        A + f"/articles/{row['id']}/media?kind=image",
        headers=key(),
        files={"file": ("poster.png", original, "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    medium = uploaded.json()
    row = admin.put(
        A + f"/articles/{row['id']}",
        headers=key(),
        json={
            "revision": row["revision"],
            "category_id": row["category_id"],
            "payload": {**row["payload"], "image_id": medium["id"]},
        },
    ).json()
    live = publish(admin, row)
    url = M + f"/articles/{row['id']}/thumbnail?version_id={live['version_id']}"
    ticket = mini.get(
        M + f"/articles/{row['id']}/thumbnail-ticket", params={"version_id": live["version_id"]}
    ).json()["url"]
    small = mini.get(url)
    assert small.status_code == 200
    with Image.open(io.BytesIO(small.content)) as image:
        assert image.size == (144, 216)
    assert int(small.headers["content-length"]) == len(small.content)
    assert len(small.content) < 20_000
    assert small.headers["cache-control"] == "no-store"
    calls = []
    previous = ObjectStorage.read

    def read(storage, storage_key):
        calls.append(storage_key)
        return previous(storage, storage_key)

    monkeypatch.setattr(ObjectStorage, "read", read)
    for path in [url, ticket]:
        partial = mini.get(path, headers={"Range": "bytes=0-15"})
        assert partial.status_code == 206
        assert partial.content == small.content[:16]
        assert partial.headers["content-range"] == f"bytes 0-15/{len(small.content)}"
        invalid = mini.get(path, headers={"Range": f"bytes={len(small.content)}-"})
        assert invalid.status_code == 416
        assert invalid.headers["content-range"] == f"bytes */{len(small.content)}"
    assert calls == []
    head = mini.head(ticket)
    assert head.status_code == 200 and head.content == b""
    assert int(head.headers["content-length"]) == len(small.content)
    assert admin.get(f"/api/admin/v1/media/{medium['id']}").content == original
    assert (
        mini.get(
            M + f"/articles/{row['id']}/media/{medium['id']}",
            params={"version_id": live["version_id"]},
        ).status_code
        == 403
    )
    bearer = mini.headers.pop("Authorization")
    assert mini.get(url).status_code == 200  # current published thumbnail is public
    mini.headers["Authorization"] = bearer
    post(admin, A + f"/articles/{row['id']}/offline", {"revision": live["revision"]})
    assert mini.get(url, headers={"Range": "bytes=0-15"}).status_code == 404
    assert mini.get(ticket, headers={"Range": "bytes=0-15"}).status_code == 404
    system["time"][0] += timedelta(minutes=6)
    assert mini.get(ticket).status_code == 401


def test_listening_home_continuation_sql_does_not_grow_per_history(admin, mini, system):
    from juya_api.listening_models import ListeningProgress

    _, ids = listening_catalog(admin, system)

    def add_progress(article_ids):
        with system["sessions"].begin() as db:
            user_id = db.scalar(select(User.id))
            for article_id in article_ids:
                row = db.get(Article, article_id)
                db.add(
                    ListeningProgress(
                        user_id=user_id,
                        article_id=row.id,
                        version_id=row.version_id,
                        reading_position=0,
                        translation_open=False,
                        audio_position=0,
                        playback_rate=1,
                        updated_at=system["time"][0],
                    )
                )

    add_progress(ids[:1])
    with sql_reads(system) as single:
        response = mini.get(M + "/home")
    assert response.status_code == 200 and response.json()["continue_learning"] is None
    add_progress(ids[1:])
    with sql_reads(system) as full:
        response = mini.get(M + "/home")
    assert response.status_code == 200 and response.json()["continue_learning"] is None
    assert len(full) <= len(single) + 1, (len(single), len(full))


@pytest.mark.parametrize("change", ["revoke", "expire"])
def test_listening_batch_access_and_flags_remain_user_and_request_scoped(
    admin, mini, system, change
):
    from juya_api.access_models import LearningAuthorization
    from juya_api.learning_service import business_date

    listening_catalog(admin, system)
    with system["sessions"].begin() as db:
        user_id = db.scalar(select(User.id))
        db.add(
            LearningAuthorization(
                user_id=user_id,
                starts_on=business_date(system["time"][0]),
                expires_on=business_date(system["time"][0]),
                revision=1,
            )
        )
    active = mini.get(M + "/articles").json()["items"]
    assert all(item["access"]["can_lookup"] for item in active)
    assert mini.get(M + "/home").json()["categories"][0]["restricted_articles"] == 0
    original_bearer = mini.headers["Authorization"]
    login = mini.post(
        "/api/mini/v1/auth/wechat",
        headers=key(),
        json={
            "code": "bob:first",
            "consent_version": "2026-10-17",
            "consent": True,
        },
    )
    assert login.status_code == 200, login.text
    mini.headers["Authorization"] = "Bearer " + login.json()["access_token"]
    other = mini.get(M + "/articles").json()["items"]
    assert all(not any(item["state"].values()) for item in other)
    assert sum(item["access"]["can_learn"] for item in other) == 6
    assert mini.get(M + "/home").json()["categories"][0]["completed_articles"] == 0
    assert not any(item["access"]["can_lookup"] for item in other)
    mini.headers["Authorization"] = original_bearer
    if change == "revoke":
        with system["sessions"].begin() as db:
            grant = db.get(LearningAuthorization, user_id)
            grant.revoked_at = system["time"][0]
            grant.revision += 1
    else:
        system["time"][0] += timedelta(days=1)
    updated = mini.get(M + "/articles").json()["items"]
    assert sum(item["access"]["can_learn"] for item in updated) == 6
    assert not any(item["access"]["can_lookup"] for item in updated)
    assert all(item["state"]["favorite"] and item["state"]["completed"] for item in updated)
    assert mini.get(M + "/home").json()["categories"][0]["restricted_articles"] == 6


def test_listening_home_aggregates_only_current_live_publications(admin, mini, system):
    from juya_api.listening_models import ListeningCategory

    owner, ids = listening_catalog(admin, system)
    with system["sessions"].begin() as db:
        db.get(Article, ids[0]).status = "draft"
        db.get(Article, ids[1]).status = "offline"
        db.get(Article, ids[2]).deleted_at = system["time"][0]
        db.get(Article, ids[3]).version_id = None
        hidden = ListeningCategory(name="已删除分类", deleted_at=system["time"][0])
        db.add(hidden)
        db.flush()
        db.get(Article, ids[4]).category_id = hidden.id
        db.add(ListeningCategory(name="无文章分类"))
    categories = mini.get(M + "/home").json()["categories"]
    assert len(categories) == 1 and categories[0]["id"] == owner["id"]
    assert (
        categories[0]["total_articles"],
        categories[0]["completed_articles"],
        categories[0]["restricted_articles"],
    ) == (7, 7, 4)
