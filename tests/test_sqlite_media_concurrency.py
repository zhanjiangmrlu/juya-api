"""The shared local database must issue image tickets under parallel list loading."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import event

from .content_helpers import draft, publish


def test_parallel_sqlite_image_tickets_keep_their_authorization_and_all_succeed(
    admin, mini, system
):
    """Simulate nine list thumbnails reading then persisting their short-lived tickets."""
    engine = system["engine"]
    if engine.dialect.name != "sqlite":
        pytest.skip("Regression for the local SQLite transaction upgrade")
    card = draft(admin)
    version = publish(admin, card)["current_version_id"]
    image = card["content"]["image_id"]
    path = f"/api/mini/v1/cards/{card['id']}/media/{image}/url?version_id={version}"
    gate = Barrier(9)
    database_errors = []

    def record_error(context):
        database_errors.append(getattr(context.original_exception, "sqlite_errorname", "unknown"))

    def fetch_image(_index):
        gate.wait(timeout=10)
        response = mini.get(path)
        if response.status_code != 200:
            return response.status_code, None
        return response.status_code, response.json()["url"]

    event.listen(engine, "handle_error", record_error)
    try:
        with ThreadPoolExecutor(max_workers=9) as pool:
            responses = list(pool.map(fetch_image, range(9)))
    finally:
        event.remove(engine, "handle_error", record_error)
    assert [status for status, _url in responses] == [200] * 9, database_errors
    urls = [url for _status, url in responses]
    assert len(set(urls)) == 9
    for url in urls:
        response = mini.get(url)
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content
    assert mini.post("/api/mini/v1/auth/logout").status_code == 200
    assert all(mini.get(url).status_code == 401 for url in urls)


def test_sqlite_read_only_cards_and_images_do_not_wait_for_an_uncommitted_writer(
    admin, mini, system
):
    """A slow writer must not block independent reads of already-published content."""
    engine = system["engine"]
    if engine.dialect.name != "sqlite":
        pytest.skip("SQLite writer reservation regression")
    card = draft(admin)
    version = publish(admin, card)["current_version_id"]
    image = card["content"]["image_id"]
    url = mini.get(
        f"/api/mini/v1/cards/{card['id']}/media/{image}/url?version_id={version}"
    ).json()["url"]
    with ThreadPoolExecutor(max_workers=1) as pool, engine.connect() as writer:
        transaction = writer.begin()
        try:
            pending = pool.submit(lambda: (mini.get("/api/mini/v1/cards"), mini.get(url)))
            responses = pending.result(timeout=1)
            assert [response.status_code for response in responses] == [200, 200]
        finally:
            transaction.rollback()


def test_sqlite_audited_admin_gets_reserve_the_writer_before_reading(admin, mini, system):
    """User-list/detail GETs still write audit records and need explicit write intent."""
    engine = system["engine"]
    if engine.dialect.name != "sqlite":
        pytest.skip("SQLite GET write-intent regression")
    user_id = mini.get("/api/mini/v1/me").json()["id"]
    intents = []

    def record_begin(connection):
        intents.append(connection.get_execution_options().get("sqlite_write_intent"))

    event.listen(engine, "begin", record_begin)
    try:
        assert admin.get("/api/admin/v1/users").status_code == 200
        assert admin.get(f"/api/admin/v1/users/{user_id}").status_code == 200
    finally:
        event.remove(engine, "begin", record_begin)
    assert intents == [True, True]
