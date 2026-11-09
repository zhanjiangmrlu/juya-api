"""Guard source-note admission atomically without changing ordinary reading semantics."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event

import pytest
from sqlalchemy import event, func, select

from .content_helpers import draft, key, process_jobs, publish
from .test_study_notes import pdf, save_note, upload


def noted_card(admin):
    note = upload(admin, pdf("entry-note"))
    process_jobs(admin)
    return publish(admin, save_note(admin, draft(admin), {"action": "set", "media_id": note["id"]}))


def starts(system):
    from juya_api.discovery_models import ReadingStart

    with system["sessions"]() as db:
        return db.scalar(select(func.count()).select_from(ReadingStart))


def guard_path(card, *, readonly=False):
    return f"/api/mini/v1/cards/{card['id']}?require_study_note=true" + (
        "&mark_started=false" if readonly else ""
    )


def removal_preview(admin, card):
    pending = save_note(admin, card, {"action": "remove"})
    preview = admin.post(
        f"/api/admin/v1/cards/{card['id']}/preview",
        headers=key(),
        json={"revision": pending["draft_revision"]},
    )
    assert preview.status_code == 200, preview.text
    return pending, preview.json()


def test_guarded_notes_detail_records_original_reading_start_once_without_scores(
    admin, mini, system
):
    from juya_api.discovery_models import ReadingStart
    from juya_api.learning_models import Checkin, Completion, DailyLearning

    card = noted_card(admin)
    before = mini.get("/api/mini/v1/me/statistics").json()
    for _ in range(2):
        result = mini.get(guard_path(card))
        assert result.status_code == 200, result.text
        assert result.json()["study_note"] and result.json()["state"]["started"]
    assert starts(system) == 1
    with system["sessions"]() as db:
        first = db.scalar(select(ReadingStart.started_at))
        for model in [Checkin, Completion, DailyLearning]:
            assert db.scalar(select(func.count()).select_from(model)) == 0
    assert mini.get(guard_path(card)).status_code == 200
    with system["sessions"]() as db:
        assert db.scalar(select(ReadingStart.started_at)) == first
    assert mini.get("/api/mini/v1/me/statistics").json() == before


@pytest.mark.parametrize("invalidate", ["remove", "media_failed"])
@pytest.mark.parametrize("readonly", [False, True])
def test_queue_candidate_losing_pdf_is_rejected_before_start_but_normal_detail_stays_compatible(
    admin, mini, system, invalidate, readonly
):
    from juya_api.content_models import Media

    card = noted_card(admin)
    queued = mini.post(
        "/api/mini/v1/learning-queues",
        headers=key(),
        json={"source": "learning_notes", "card_id": card["id"]},
    )
    assert queued.status_code == 201
    assert mini.get("/api/mini/v1/learning-queues/" + queued.json()["id"]).json()["items"][0][
        "available"
    ]
    assert starts(system) == 0
    if invalidate == "remove":
        latest = publish(admin, save_note(admin, card, {"action": "remove"}))
        assert latest["current_version_id"] == card["current_version_id"]
    else:
        with system["sessions"].begin() as db:
            db.get(Media, card["published_study_note"]["media_id"]).state = "failed"
    rejected = mini.get(guard_path(card, readonly=readonly))
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["error"]["code"] == "study_note_unavailable"
    assert starts(system) == 0
    normal = mini.get(f"/api/mini/v1/cards/{card['id']}")
    assert normal.status_code == 200 and normal.json()["study_note"] is None
    assert starts(system) == 1


def test_guarded_readonly_probe_never_records_start_and_valid_replacement_still_enters(
    admin, mini, system
):
    card = noted_card(admin)
    before = mini.get("/api/mini/v1/me/statistics").json()
    read = mini.get(guard_path(card, readonly=True))
    assert read.status_code == 200 and not read.json()["state"]["started"]
    assert starts(system) == 0
    replacement = upload(admin, pdf("replacement"))
    process_jobs(admin)
    updated = publish(
        admin, save_note(admin, card, {"action": "set", "media_id": replacement["id"]})
    )
    assert updated["current_version_id"] == card["current_version_id"]
    entered = mini.get(guard_path(card))
    assert entered.status_code == 200
    assert (
        entered.json()["study_note"]["version_id"] == updated["published_study_note"]["version_id"]
    )
    assert starts(system) == 1 and mini.get("/api/mini/v1/me/statistics").json() == before


def test_default_learning_source_accepts_no_pdf_and_explicit_false_matches_original(
    admin, mini, system
):
    card = publish(admin, draft(admin))
    queued = mini.post(
        "/api/mini/v1/learning-queues",
        headers=key(),
        json={"source": "learning", "card_id": card["id"]},
    )
    assert queued.status_code == 201
    assert mini.get("/api/mini/v1/learning-queues/" + queued.json()["id"]).json()["items"][0][
        "available"
    ]
    result = mini.get(f"/api/mini/v1/cards/{card['id']}?require_study_note=false")
    assert result.status_code == 200 and result.json()["study_note"] is None
    assert starts(system) == 1


@pytest.mark.parametrize(
    "invalidation,expected",
    [("offline", 410), ("delete", 410), ("free_closed", 403), ("revoke", 403)],
)
def test_guarded_detail_still_rechecks_current_publication_and_permission(
    admin, mini, system, invalidation, expected
):
    from .test_learning_access import change, user_id

    card = noted_card(admin)
    if invalidation == "revoke":
        change(admin, user_id(mini), "grant")
    if invalidation in {"free_closed", "revoke"}:
        path = f"/api/admin/v1/cards/{card['id']}/free-access"
        current = admin.get(path).json()
        assert (
            admin.put(
                path, headers=key(), json={"is_free": False, "revision": current["revision"]}
            ).status_code
            == 200
        )
        if invalidation == "revoke":
            change(admin, user_id(mini), "revoke")
    else:
        response = admin.request(
            "DELETE" if invalidation == "delete" else "POST",
            f"/api/admin/v1/cards/{card['id']}" + ("/offline" if invalidation == "offline" else ""),
            headers=key(),
            json={"revision": card["draft_revision"]},
        )
        assert response.status_code == 200
    assert mini.get(guard_path(card)).status_code == expected
    assert starts(system) == 0


@pytest.mark.mysql
def test_mysql_removal_committing_while_guard_waits_cannot_create_a_reading_start(
    admin, mini, system
):
    if system["engine"].dialect.name != "mysql":
        pytest.skip("Dedicated local MySQL required")
    card = noted_card(admin)
    pending, preview = removal_preview(admin, card)
    pointer_written, contender_waiting, release = Event(), Event(), Event()

    def hold_publication(connection, cursor, statement, parameters, context, many):
        if "UPDATE cards SET" in statement and "current_study_note_version_id" in statement:
            pointer_written.set()
            assert release.wait(10)

    def observe_contender(connection, cursor, statement, parameters, context, many):
        upper = statement.upper()
        shared_catalog = "SETTING_COUNTERS" in upper and (
            "LOCK IN SHARE MODE" in upper or "FOR SHARE" in upper
        )
        if shared_catalog or "INSERT INTO READING_STARTS" in upper:
            contender_waiting.set()

    engine = system["engine"]
    event.listen(engine, "after_cursor_execute", hold_publication)
    event.listen(engine, "before_cursor_execute", observe_contender)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            try:
                publisher = pool.submit(
                    admin.post,
                    f"/api/admin/v1/cards/{card['id']}/publish",
                    headers=key(),
                    json={
                        "revision": pending["draft_revision"],
                        "preview_id": preview["preview_id"],
                    },
                )
                assert pointer_written.wait(5)
                reading = pool.submit(mini.get, guard_path(card))
                assert contender_waiting.wait(5)
                release.set()
                assert publisher.result(timeout=15).status_code == 200
                rejected = reading.result(timeout=15)
            finally:
                release.set()
    finally:
        event.remove(engine, "after_cursor_execute", hold_publication)
        event.remove(engine, "before_cursor_execute", observe_contender)
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["error"]["code"] == "study_note_unavailable"
    assert starts(system) == 0


@pytest.mark.mysql
@pytest.mark.parametrize("mutation", ["remove", "invalidate"])
def test_mysql_guard_holds_admission_until_start_insert_before_pdf_removal(
    admin, mini, system, mutation
):
    if system["engine"].dialect.name != "mysql":
        pytest.skip("Dedicated local MySQL required")
    card = noted_card(admin)
    pending, preview = removal_preview(admin, card)
    before_insert, release, publisher_at_lock = Event(), Event(), Event()

    def pause_admission(connection, cursor, statement, parameters, context, many):
        upper = statement.upper()
        if "INSERT INTO READING_STARTS" in upper:
            before_insert.set()
            assert release.wait(10)
        if (
            "SETTING_COUNTERS" in upper and ("FOR UPDATE" in upper or "INSERT INTO" in upper)
        ) or "UPDATE MEDIA SET" in upper:
            publisher_at_lock.set()

    engine = system["engine"]
    event.listen(engine, "before_cursor_execute", pause_admission)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            try:
                reading = pool.submit(mini.get, guard_path(card))
                assert before_insert.wait(5)

                def mutate():
                    if mutation == "remove":
                        return admin.post(
                            f"/api/admin/v1/cards/{card['id']}/publish",
                            headers=key(),
                            json={
                                "revision": pending["draft_revision"],
                                "preview_id": preview["preview_id"],
                            },
                        )
                    from sqlalchemy import update

                    from juya_api.content_models import Media

                    with system["sessions"].begin() as db:
                        db.execute(
                            update(Media)
                            .where(Media.id == card["published_study_note"]["media_id"])
                            .values(state="failed")
                        )

                publisher = pool.submit(mutate)
                assert publisher_at_lock.wait(5)
                with pytest.raises(TimeoutError):
                    publisher.result(timeout=0.3)
                release.set()
                assert reading.result(timeout=15).status_code == 200
                outcome = publisher.result(timeout=15)
                if mutation == "remove":
                    assert outcome.status_code == 200
            finally:
                release.set()
    finally:
        event.remove(engine, "before_cursor_execute", pause_admission)
    assert starts(system) == 1
    assert mini.get(guard_path(card)).status_code == 409


@pytest.mark.mysql
def test_mysql_revocation_committing_before_guard_admission_does_not_write_start(
    admin, mini, system
):
    from .test_learning_access import change, user_id

    if system["engine"].dialect.name != "mysql":
        pytest.skip("Dedicated local MySQL required")
    card = noted_card(admin)
    uid = user_id(mini)
    change(admin, uid, "grant")
    free_path = f"/api/admin/v1/cards/{card['id']}/free-access"
    current = admin.get(free_path).json()
    assert (
        admin.put(
            free_path, headers=key(), json={"is_free": False, "revision": current["revision"]}
        ).status_code
        == 200
    )
    path = f"/api/admin/v1/users/{uid}/learning-authorization"
    token = admin.post(path + "/preview", json={"action": "revoke"}).json()["preview_token"]
    changed, contender, release = Event(), Event(), Event()

    def hold_revoke(connection, cursor, statement, parameters, context, many):
        if "UPDATE learning_authorizations" in statement:
            changed.set()
            assert release.wait(10)

    def observe(connection, cursor, statement, parameters, context, many):
        upper = statement.upper()
        if (
            "FROM USERS" in upper and "FOR UPDATE" in upper
        ) or "INSERT INTO READING_STARTS" in upper:
            contender.set()

    engine = system["engine"]
    event.listen(engine, "after_cursor_execute", hold_revoke)
    event.listen(engine, "before_cursor_execute", observe)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            try:
                revoke = pool.submit(admin.put, path, headers=key(), json={"preview_token": token})
                assert changed.wait(5)
                # Ignore the administrator's own User lock, observed before UPDATE.
                contender.clear()
                reading = pool.submit(mini.get, guard_path(card))
                assert contender.wait(5)
                release.set()
                assert revoke.result(timeout=15).status_code == 200
                result = reading.result(timeout=15)
            finally:
                release.set()
    finally:
        event.remove(engine, "after_cursor_execute", hold_revoke)
        event.remove(engine, "before_cursor_execute", observe)
    assert result.status_code == 403, result.text
    assert starts(system) == 0
