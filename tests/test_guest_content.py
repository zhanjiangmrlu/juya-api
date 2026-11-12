"""Guest HTTP contracts use real publications, storage, SQL facts and worker jobs."""

from datetime import timedelta

import pytest
from sqlalchemy import event, func, select

from juya_api.content_models import Card
from juya_api.database import Base
from juya_api.job_models import Job
from tests.content_helpers import content, draft, key, process_jobs, publish
from tests.test_listening import M, article, policy
from tests.test_listening import publish as publish_article
from tests.test_study_notes import pdf, save_note, upload

P = "/api/mini/v1"


def set_free(admin, identifier, enabled, *, listening=False):
    path = "/api/admin/v1/listening/articles/" if listening else "/api/admin/v1/cards/"
    path += identifier + "/free-access"
    current = admin.get(path).json()
    result = admin.put(
        path, json={"is_free": enabled, "revision": current["revision"]}, headers=key()
    )
    assert result.status_code == 200, result.text


def personal_counts(system):
    tables = [
        t
        for t in Base.metadata.sorted_tables
        if t.name
        in {
            "users",
            "mini_sessions",
            "media_tickets",
            "learning_authorizations",
            "learning_queues",
            "learning_queue_items",
            "login_operations",
            "consents",
            "reading_starts",
            "completions",
            "daily_learning",
            "favorites",
            "checkins",
            "operations",
            "listening_progress",
            "listening_completions",
            "listening_daily",
            "listening_favorites",
        }
    ]
    with system["sessions"]() as db:
        return {
            t.name: db.scalar(
                select(func.count()).select_from(t).where(t.c.scope.like("mini:%"))
                if t.name == "operations"
                else select(func.count()).select_from(t)
            )
            for t in tables
        }


def test_guest_scene_catalog_detail_and_summary_never_read_or_create_personal_facts(admin, system):
    payload = content(admin)
    free, restricted = [publish(admin, draft(admin, {**payload, "name": str(i)})) for i in range(2)]
    set_free(admin, restricted["id"], False)
    guest = system["mini"]
    before = personal_counts(system)
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())

    event.listen(system["engine"], "before_cursor_execute", capture)
    try:
        listing = guest.get(P + "/cards?scope=uncompleted&limit=1&page=99")
        assert listing.status_code == 200, listing.text
        data = listing.json()
        assert data["total"] == data["published_total"] == 2 and data["page"] == 2
        assert data["free_uncompleted_total"] is None
        assert data["learning_access"]["authorization"] is None
        assert data["items"][0]["state"] is None
        detail = guest.get(P + f"/cards/{free['id']}?mark_started=true")
        assert detail.status_code == 200, detail.text
        assert detail.json()["state"] is None and detail.json()["reading_position"] is None
        assert detail.json()["access"]["can_lookup"] is False
        assert guest.get(P + f"/cards/{restricted['id']}").status_code == 403
        summary = guest.get(P + f"/cards/{restricted['id']}/summary")
        assert summary.status_code == 200, summary.text
        assert summary.json()["state"] is None and summary.json()["access"]["can_learn"] is False
        assert (
            not {"content", "study_note", "audio_id", "image_id", "vocabulary"}
            & summary.json().keys()
        )
    finally:
        event.remove(system["engine"], "before_cursor_execute", capture)
    assert not any(any(f" {name}" in s for name in before) for s in statements), statements
    assert personal_counts(system) == before


@pytest.mark.parametrize("header", ["Bearer mini_invalid", "Basic invalid", "Bearer adm_invalid"])
def test_invalid_identity_is_never_silently_downgraded_to_guest(admin, system, header):
    card = publish(admin, draft(admin))
    for path in [
        "/cards",
        f"/cards/{card['id']}",
        f"/cards/{card['id']}/summary",
        "/listening/home",
        "/listening/articles",
    ]:
        assert system["mini"].get(P + path, headers={"Authorization": header}).status_code == 401


def test_guest_listening_catalog_and_detail_have_null_personal_fields(admin, system):
    free, restricted = [publish_article(admin, article(admin, title=str(i))) for i in range(2)]
    policy(admin, 2)
    set_free(admin, restricted["id"], False, listening=True)
    guest = system["mini"]
    before = personal_counts(system)
    response = guest.get(M + "/home")
    assert response.status_code == 200, response.text
    home = response.json()
    assert home["authorization"] is home["statistics"] is home["continue_learning"] is None
    assert all(c["completed_articles"] is None for c in home["categories"])
    listed = guest.get(M + "/articles").json()
    assert listed["total"] == 2 and all(x["state"] is None for x in listed["items"])
    response = guest.get(M + f"/articles/{free['id']}")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["state"] is data["progress"] is data["queue_token"] is None
    assert guest.get(M + f"/articles/{restricted['id']}").status_code == 403
    summary = guest.get(M + f"/articles/{restricted['id']}/summary").json()
    assert (
        not {"payload", "body_en", "vocabulary", "expressions", "audio_id", "image_id"}
        & summary.keys()
    )
    assert personal_counts(system) == before
    assert (
        guest.get(
            M + f"/articles/{free['id']}/dictionary",
            params={"version_id": free["version_id"], "start": 0, "end": 2},
        ).status_code
        == 401
    )
    assert (
        guest.post(
            P + "/learning-queues",
            json={"source": "scene_list", "card_id": free["id"]},
            headers=key(),
        ).status_code
        == 401
    )


@pytest.mark.parametrize("method", ["GET", "HEAD", "RANGE"])
def test_public_scene_tickets_recheck_free_and_expiry_for_each_request(admin, system, method):
    card = publish(admin, draft(admin))
    guest = system["mini"]
    response = guest.get(
        P + f"/cards/{card['id']}/media/{card['content']['image_id']}/url",
        params={"version_id": card["current_version_id"]},
    )
    assert response.status_code == 200, response.text
    grant = response.json()

    def fetch():
        return guest.request(
            "GET" if method == "RANGE" else method,
            grant["url"],
            headers={"Range": "bytes=0-3"} if method == "RANGE" else {},
        )

    assert fetch().status_code == (206 if method == "RANGE" else 200)
    assert fetch().headers["cache-control"] == "no-store"
    set_free(admin, card["id"], False)
    assert fetch().status_code == 403
    set_free(admin, card["id"], True)
    assert fetch().status_code in {200, 206}
    system["time"][0] += timedelta(seconds=300)
    assert fetch().status_code == 401


def test_private_note_ticket_is_version_bound_and_restricted_summary_is_thumbnail_only(
    admin, mini, system
):
    medium = upload(admin)
    process_jobs(admin)
    card = publish(
        admin, save_note(admin, draft(admin), {"action": "set", "media_id": medium["id"]})
    )
    guest = mini
    note = guest.get(P + f"/cards/{card['id']}").json()["study_note"]
    path = P + f"/cards/{card['id']}/media/{note['media_id']}/url"
    result = guest.get(
        path, params={"purpose": "study_note", "study_note_version_id": note["version_id"]}
    )
    assert result.status_code == 200, result.text
    url = result.json()["url"]
    assert guest.get(url).content == pdf()
    removed = publish(admin, save_note(admin, card, {"action": "remove"}))
    assert guest.get(url).status_code == guest.head(url).status_code == 409
    assert guest.get(url, headers={"Range": "bytes=0-3"}).status_code == 409
    set_free(admin, card["id"], False)
    summary = guest.get(P + f"/cards/{card['id']}/summary").json()
    thumbnail = guest.get(
        P + f"/cards/{card['id']}/media/{summary['thumbnail_id']}/url",
        params={"purpose": "summary", "version_id": removed["current_version_id"]},
    )
    assert thumbnail.status_code == 200, thumbnail.text
    assert guest.get(thumbnail.json()["url"]).status_code == 200
    assert guest.get(path, params={"purpose": "summary"}).status_code == 404
    assert guest.get(P + "/cards?has_study_note=true").json()["total"] == 0


def test_private_listening_tickets_recheck_current_version_and_free(admin, mini, system):
    live = publish_article(admin, article(admin))
    policy(admin, 1)
    guest = mini
    response = guest.post(
        M + f"/articles/{live['id']}/media-ticket",
        json={"version_id": live["version_id"], "media_id": live["payload"]["audio_id"]},
        headers=key(),
    )
    assert response.status_code == 200, response.text
    url = response.json()["url"]
    assert guest.head(url).status_code == 200
    set_free(admin, live["id"], False, listening=True)
    assert guest.get(url, headers={"Range": "bytes=0-3"}).status_code == 403
    assert guest.head(url).status_code == 403


def test_guest_pronunciation_rejects_without_users_jobs_or_personal_operations(admin, system):
    card = publish(admin, draft(admin))
    guest = system["mini"]
    before = personal_counts(system)
    with system["sessions"]() as db:
        jobs_before = db.scalar(select(func.count()).select_from(Job))
    path = P + f"/cards/{card['id']}/words/word-1/pronunciation"
    body = {"version_id": card["current_version_id"]}
    for response in [guest.get(path, params=body), guest.post(path, json=body, headers=key())]:
        assert response.status_code == 401, response.text
        assert response.json()["error"]["code"] == "unauthenticated"
    with system["sessions"]() as db:
        assert db.scalar(select(func.count()).select_from(Job)) == jobs_before
    assert personal_counts(system) == before


def test_private_speech_worker_ready_delivery_dedup_cooldown_and_live_revocation(
    admin, mini, system
):
    from juya_api.worker import run_job
    from tests.content_helpers import recording

    card = publish(admin, draft(admin))
    guest = mini
    path = P + f"/cards/{card['id']}/words/word-1/pronunciation"
    body = {"version_id": card["current_version_id"]}
    assert guest.get(path, params=body).json()["state"] in {"missing", "processing"}
    job_id = guest.post(path, json=body, headers=key()).json()["job_id"]
    calls = []

    class Provider:
        def synthesize(self, text, config, session):
            calls.append(text)
            return recording()

    run_job(
        system["settings"], system["sessions"], job_id, clock=admin.app.state.clock, tts=Provider()
    )
    ready = guest.get(path, params=body).json()
    assert ready["state"] == "ready" and calls == ["coffee"]
    assert ready["url"].startswith(P + "/pronunciation/")
    for method, headers, status in [
        ("GET", {}, 200),
        ("HEAD", {}, 200),
        ("GET", {"Range": "bytes=0-3"}, 206),
    ]:
        response = guest.request(method, ready["url"], headers=headers)
        assert response.status_code == status
        assert response.headers["cache-control"] == "no-store"
    assert guest.post(path, json=body, headers=key()).json()["job_id"] == job_id
    set_free(admin, card["id"], False)
    for method in ["GET", "HEAD"]:
        assert (
            guest.request(method, ready["url"], headers={"Range": "bytes=0-3"}).status_code == 403
        )


def test_private_listening_preset_speech_never_accepts_body_positions_or_draft_words(
    admin, mini, system
):
    from juya_api.worker import run_job
    from tests.content_helpers import recording

    draft_article = article(admin)
    payload = {
        **draft_article["payload"],
        "vocabulary": [{"id": "preset-rest", "english": "rest", "meaning": "休息"}],
    }
    changed = admin.put(
        "/api/admin/v1/listening/articles/" + draft_article["id"],
        headers=key(),
        json={
            "revision": draft_article["revision"],
            "category_id": draft_article["category_id"],
            "payload": payload,
        },
    )
    assert changed.status_code == 200, changed.text
    live = publish_article(admin, changed.json())
    policy(admin, 1)
    guest = mini
    path = M + f"/articles/{live['id']}/words/preset-rest/pronunciation"
    ref = {"version_id": live["version_id"]}
    response = guest.post(path, json=ref, headers=key())
    assert response.status_code == 200, response.text
    job_id = response.json()["job_id"]

    class Provider:
        def synthesize(self, text, config, session):
            assert text == "rest"
            return recording()

    run_job(
        system["settings"], system["sessions"], job_id, clock=admin.app.state.clock, tts=Provider()
    )
    ready = guest.get(path, params=ref).json()
    assert ready["state"] == "ready"
    assert guest.get(ready["url"]).status_code == 200
    assert guest.post(path, json={**ref, "start": 0, "end": 2}, headers=key()).status_code == 422
    assert guest.post(path.replace("preset-rest", "We"), json=ref, headers=key()).status_code == 404
    assert guest.get(path, params={"revision": live["revision"]}).status_code == 422
    set_free(admin, live["id"], False, listening=True)
    assert guest.head(ready["url"]).status_code == 403


def test_raw_valid_token_is_an_invalid_supplied_authorization(admin, mini, system):
    token = mini.headers["Authorization"].removeprefix("Bearer ")
    response = mini.get(P + "/cards", headers={"Authorization": token})
    assert response.status_code == 401


def test_public_ticket_rejects_sealed_wrong_purpose_and_format_without_private_fallback(
    admin, mini, system
):
    import json

    from juya_api.security import decrypt, encrypt

    card = publish(admin, draft(admin))
    params = {"version_id": card["current_version_id"]}
    path = P + f"/cards/{card['id']}/media/{card['content']['image_id']}/url"
    private = mini.get(path, params=params).json()["url"]
    mini.headers.pop("Authorization")
    public = mini.get(path, params=params).json()["url"]
    assert mini.get(private).status_code == 200  # existing non-PDF session-bound behavior
    # The public route cannot accept even a valid private med_ token.
    assert mini.get(P + "/public/resources/" + private.rsplit("/", 1)[1]).status_code == 401
    raw = public.rsplit("pub1_", 1)[1]
    sealed = json.loads(decrypt(system["settings"], raw))
    for field, value in [("purpose", "scene:dictionary"), ("format", "other"), ("media_id", None)]:
        forged = {**sealed, field: value}
        url = P + "/public/resources/pub1_" + encrypt(system["settings"], json.dumps(forged))
        assert mini.get(url).status_code in {401, 404}
    # Wrong private prefix never triggers anonymous fallback, even with valid public ciphertext.
    assert mini.get(P + "/media/med_" + raw).status_code == 401


@pytest.mark.parametrize("action", ["offline", "delete", "replace"])
def test_private_scene_and_listening_urls_revoke_on_publication_change(admin, mini, system, action):
    card = publish(admin, draft(admin))
    live = publish_article(admin, article(admin))
    policy(admin, 1)
    guest = mini
    card_url = guest.get(
        P + f"/cards/{card['id']}/media/{card['content']['audio_id']}/url",
        params={"version_id": card["current_version_id"]},
    ).json()["url"]
    listening_url = guest.post(
        M + f"/articles/{live['id']}/media-ticket",
        json={"version_id": live["version_id"], "media_id": live["payload"]["audio_id"]},
        headers=key(),
    ).json()["url"]
    if action == "replace":
        scene = admin.put(
            "/api/admin/v1/cards/" + card["id"],
            headers=key(),
            json={
                "revision": card["draft_revision"],
                "content": {**card["content"], "name": "更新"},
            },
        )
        assert scene.status_code == 200
        publish(admin, scene.json())
        listening = admin.put(
            "/api/admin/v1/listening/articles/" + live["id"],
            headers=key(),
            json={
                "revision": live["revision"],
                "category_id": live["category_id"],
                "payload": {**live["payload"], "title_zh": "更新"},
            },
        )
        assert listening.status_code == 200
        publish_article(admin, listening.json())
    else:
        if action == "delete":
            result = admin.request(
                "DELETE",
                "/api/admin/v1/cards/" + card["id"],
                headers=key(),
                json={"revision": card["draft_revision"]},
            )
        else:
            result = admin.post(
                "/api/admin/v1/cards/" + card["id"] + "/offline",
                headers=key(),
                json={"revision": card["draft_revision"]},
            )
        assert result.status_code == 200
        result = admin.post(
            "/api/admin/v1/listening/articles/" + live["id"] + "/" + action,
            headers=key(),
            json={"revision": live["revision"]},
        )
        assert result.status_code == 200
    for url in [card_url, listening_url]:
        for method, headers in [("GET", {}), ("HEAD", {}), ("GET", {"Range": "bytes=0-3"})]:
            assert guest.request(method, url, headers=headers).status_code in {403, 404, 409, 410}


def test_guest_notes_are_all_published_valid_notes_before_pagination(admin, mini, system):
    base = content(admin)
    media = upload(admin)
    process_jobs(admin)
    cards = [
        publish(
            admin,
            save_note(
                admin,
                draft(admin, {**base, "name": str(i)}),
                {"action": "set", "media_id": media["id"]},
            ),
        )
        for i in range(3)
    ]
    assert (
        mini.post(
            P + f"/cards/{cards[0]['id']}/complete",
            headers=key(),
            json={"version_id": cards[0]["current_version_id"]},
        ).status_code
        == 200
    )
    mini.headers.pop("Authorization")
    response = mini.get(P + "/cards?scope=uncompleted&has_study_note=true&limit=1&page=99")
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 3 and response.json()["page"] == 3
    with system["sessions"].begin() as db:
        db.get(Card, cards[2]["id"]).status = "offline"
    response = mini.get(P + "/cards?scope=uncompleted&has_study_note=true&limit=1&page=99").json()
    assert response["total"] == response["page"] == 2


def test_guest_current_summary_and_owned_history_remain_separate(admin, mini, system):
    from juya_api.models import MiniSession
    from juya_api.security import digest

    card = publish(admin, draft(admin))
    assert mini.get(P + f"/cards/{card['id']}/summary").status_code == 200
    assert (
        mini.post(
            P + f"/cards/{card['id']}/complete",
            headers=key(),
            json={"version_id": card["current_version_id"]},
        ).status_code
        == 200
    )
    current_token = mini.headers.pop("Authorization")
    system["admin"].post(
        f"/api/admin/v1/cards/{card['id']}/offline",
        headers=key(),
        json={"revision": card["draft_revision"]},
    )
    assert mini.get(P + f"/cards/{card['id']}/summary").status_code == 404
    assert (
        mini.get(
            P + f"/cards/{card['id']}/summary", headers={"Authorization": current_token}
        ).status_code
        == 200
    )
    with system["sessions"].begin() as db:
        db.get(MiniSession, digest(current_token.removeprefix("Bearer "))).expires_at = system[
            "time"
        ][0]
    assert mini.get(P + "/cards", headers={"Authorization": current_token}).status_code == 401
    assert mini.get(P + "/cards").status_code == 200


def test_legacy_public_pronunciation_worker_never_looks_up_a_user(admin, system):
    from juya_api.worker import run_job
    from tests.content_helpers import recording

    card = publish(admin, draft(admin))
    system["settings"].tts_voice_type += 1  # independent cache key, not publication prewarm
    from juya_api.pronunciation import reference, request_for_owner

    with system["sessions"].begin() as db:
        word, reading, config, cache_key = reference(
            db, system["settings"], "mini", card["id"], "word-1", card["current_version_id"]
        )
        job_id = request_for_owner(
            db,
            system["settings"],
            "public-pronunciation",
            "mini",
            word,
            reading,
            config,
            cache_key,
            system["time"][0],
        )["job_id"]
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())

    class Provider:
        def synthesize(self, text, config, session):
            return recording()

    system["settings"].worker_role = "mini"
    event.listen(system["engine"], "before_cursor_execute", capture)
    try:
        run_job(
            system["settings"],
            system["sessions"],
            job_id,
            clock=admin.app.state.clock,
            tts=Provider(),
        )
    finally:
        event.remove(system["engine"], "before_cursor_execute", capture)
    assert not any("from users" in statement for statement in statements)
    with system["sessions"]() as db:
        assert db.get(Job, job_id).state == "succeeded"


def test_public_grant_malformed_media_reference_is_rejected_without_server_error(admin, system):
    import json

    from juya_api.security import decrypt, encrypt

    card = publish(admin, draft(admin))
    guest = system["mini"]
    url = guest.get(
        P + f"/cards/{card['id']}/media/{card['content']['image_id']}/url",
        params={"version_id": card["current_version_id"]},
    ).json()["url"]
    data = json.loads(decrypt(system["settings"], url.rsplit("pub1_", 1)[1]))
    for change in [
        {"media_id": []},
        {"expires": float("nan")},
        {"purpose": "scene:word", "word_id": None},
    ]:
        sealed = encrypt(system["settings"], json.dumps({**data, **change}))
        response = guest.get(P + "/public/resources/pub1_" + sealed)
        assert response.status_code == 401, response.text


def test_private_speech_failed_job_obeys_shared_cooldown(admin, mini, system):
    from juya_api.errors import DomainError
    from juya_api.worker import run_job

    card = publish(admin, draft(admin))
    guest = mini
    ref = {"version_id": card["current_version_id"]}
    path = P + f"/cards/{card['id']}/words/word-1/pronunciation"
    job_id = guest.post(path, json=ref, headers=key()).json()["job_id"]

    class Provider:
        def synthesize(self, text, config, session):
            raise DomainError(422, "tts_permanent", "no provider")

    run_job(
        system["settings"], system["sessions"], job_id, clock=admin.app.state.clock, tts=Provider()
    )
    assert guest.get(path, params=ref).json()["state"] == "failed"
    assert guest.post(path, json=ref, headers=key()).status_code == 429
    system["time"][0] += timedelta(seconds=61)
    retry = guest.post(path, json=ref, headers=key())
    assert retry.status_code == 200, retry.text
    assert retry.json()["job_id"] != job_id


def test_public_listening_thumbnail_ticket_reuses_small_cached_thumbnail_profile(admin, system):
    from tests.content_helpers import picture

    live = article(admin)
    uploaded = admin.post(
        "/api/admin/v1/listening/articles/" + live["id"] + "/media?kind=image",
        headers=key(),
        files={"file": ("image.png", picture(), "image/png")},
    ).json()
    changed = admin.put(
        "/api/admin/v1/listening/articles/" + live["id"],
        headers=key(),
        json={
            "revision": live["revision"],
            "category_id": live["category_id"],
            "payload": {**live["payload"], "image_id": uploaded["id"]},
        },
    ).json()
    live = publish_article(admin, changed)
    guest = system["mini"]
    path = M + f"/articles/{live['id']}"
    direct = guest.get(path + "/thumbnail", params={"version_id": live["version_id"]})
    grant = guest.get(path + "/thumbnail-ticket", params={"version_id": live["version_id"]})
    assert grant.status_code == 200, grant.text
    assert guest.get(grant.json()["url"]).content == direct.content


def test_guest_listening_reads_do_not_query_personal_learning_tables(admin, system):
    live = publish_article(admin, article(admin))
    policy(admin, 1)
    guest = system["mini"]
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())

    event.listen(system["engine"], "before_cursor_execute", capture)
    try:
        for suffix in [
            "/home",
            "/topics",
            "/articles",
            f"/articles/{live['id']}",
            f"/articles/{live['id']}/summary",
        ]:
            response = guest.get(M + suffix)
            assert response.status_code == 200, response.text
    finally:
        event.remove(system["engine"], "before_cursor_execute", capture)
    tables = [
        "users",
        "mini_sessions",
        "learning_authorizations",
        "listening_progress",
        "listening_favorites",
        "listening_completions",
        "listening_daily",
        "completions",
        "favorites",
        "reading_starts",
    ]
    assert not any(
        any("from " + table in query or "join " + table in query for table in tables)
        for query in statements
    ), statements
