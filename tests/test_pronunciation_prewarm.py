"""Publication warmup remains durable, exact and lower priority than interactive speech."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from juya_api.job_models import Job
from juya_api.jobs import claim, dispatch, enqueue
from juya_api.pronunciation_models import Pronunciation
from juya_api.worker import run_job

from .content_helpers import draft, key, publish, recording


def jobs(system, kind):
    with system["sessions"]() as db:
        return db.scalars(select(Job).where(Job.kind == kind)).all()


def run(system, job_id, provider=None):
    run_job(
        system["settings"],
        system["sessions"],
        job_id,
        clock=system["admin"].app.state.clock,
        tts=provider,
    )


def test_publish_accepts_one_idempotent_warmup_and_rolls_back_with_publication(admin, system):
    card = draft(admin)
    publish(admin, card)
    assert len(jobs(system, "pronunciation.prewarm")) == 1
    publish(admin, card)
    assert len(jobs(system, "pronunciation.prewarm")) == 1
    import pytest

    from juya_api.content_models import Card
    from juya_api.content_service import publish_version
    from juya_api.models import Administrator

    candidate = draft(admin)
    preview = admin.post(
        f"/api/admin/v1/cards/{candidate['id']}/preview", headers=key(), json={"revision": 1}
    ).json()
    with pytest.raises(RuntimeError), system["sessions"].begin() as db:
        publish_version(
            db,
            db.get(Card, candidate["id"]),
            db.scalar(select(Administrator.id)),
            1,
            preview["preview_id"],
            system["time"][0].replace(tzinfo=None),
            settings=system["settings"],
        )
        assert len(db.scalars(select(Job).where(Job.kind == "pronunciation.prewarm")).all()) == 2
        raise RuntimeError("rollback")
    with system["sessions"]() as db:
        assert db.get(Card, candidate["id"]).status == "draft"
        assert db.get(Card, candidate["id"]).current_version_id is None
    assert len(jobs(system, "pronunciation.prewarm")) == 1


@pytest.mark.usefixtures("legacy_learning_features")
def test_warmup_exact_utf16_context_readings_and_foreground_promotion(admin, mini, system):
    from .test_learning_access import change, user_id

    change(admin, user_id(mini), "grant")
    card = draft(admin)
    payload = card["content"]
    payload["dialogue"][0]["english"] = "😀 read read coffee"
    payload["vocabulary"] = [
        {
            "id": "past",
            "english": "read",
            "meaning": "读过",
            "pronunciation_text": "red",
            "source": {"line_id": "line-1", "start": 3, "end": 7, "quote": "read"},
        },
        {
            "id": "present",
            "english": "read",
            "meaning": "读",
            "pronunciation_text": "reed",
            "source": {"line_id": "line-1", "start": 8, "end": 12, "quote": "read"},
        },
    ]
    updated = admin.put(
        f"/api/admin/v1/cards/{card['id']}", headers=key(), json={"revision": 1, "content": payload}
    )
    assert updated.status_code == 200, updated.text
    version = publish(admin, updated.json())["current_version_id"]
    warmups = jobs(system, "pronunciation.prewarm")
    assert len(warmups) == 1
    run(system, warmups[0].id)
    children = jobs(system, "tts.prewarm")
    assert len(children) == 3
    with system["sessions"]() as db:
        assert {row.reading for row in db.scalars(select(Pronunciation))} == {
            "red",
            "reed",
            "coffee",
        }
    ref = {"version_id": version, "line_id": "line-1", "word": "read", "start": 3, "end": 7}
    response = mini.post(
        f"/api/mini/v1/cards/{card['id']}/dictionary/pronunciation", headers=key(), json=ref
    )
    assert response.status_code == 200, response.text
    promoted = response.json()["job_id"]
    with system["sessions"]() as db:
        assert db.get(Job, promoted).kind == "tts.synthesize"
        replaced = [db.get(Job, row.id) for row in children]
        assert (
            sum(
                bool(row.state == "succeeded" and (row.result or {}).get("skipped"))
                for row in replaced
            )
            == 1
        )
    calls = []

    class Provider:
        def synthesize(self, text, *_):
            calls.append(text)
            return recording()

    run(system, promoted, Provider())
    for child in children:
        run(system, child.id, Provider())
    assert calls.count("red") == 1


def test_obsolete_configuration_or_publication_never_calls_provider(admin, system):
    card = draft(admin)
    publish(admin, card)
    warmups = jobs(system, "pronunciation.prewarm")
    assert len(warmups) == 1
    run(system, warmups[0].id)
    children = jobs(system, "tts.prewarm")
    assert children
    system["settings"].tts_codec = "wav"

    class Provider:
        def synthesize(self, *_):
            raise AssertionError("obsolete warmup reached provider")

    for child in children:
        run(system, child.id, Provider())
    with system["sessions"]() as db:
        for child in children:
            row = db.get(Job, child.id)
            assert row.state == "succeeded" and row.result["skipped"]


def test_dispatch_prefers_interactive_and_retains_one_admitted_slot_across_redelivery(system):
    now = system["time"][0]
    sessions, settings = system["sessions"], system["settings"]
    with sessions.begin() as db:
        warm = [
            enqueue(db, "tts.prewarm", "mini", "actor", {}, now, settings=settings).id
            for _ in range(3)
        ]
        interactive = enqueue(db, "tts.synthesize", "mini", "actor", {}, now, settings=settings).id
    warm.sort()
    sent = []
    assert dispatch(sessions, now, sent.append, role="mini") == 2
    assert sent == [interactive, warm[0]]
    assert dispatch(sessions, now + timedelta(seconds=31), sent.append, role="mini") == 2
    assert sent[-2:] == [interactive, warm[0]]
    assert claim(sessions, warm[1], now, settings=settings, role="mini") is None
    with sessions() as db:
        assert db.get(Job, warm[1]).attempts == 0


def test_warmup_batches_and_invalid_reading_does_not_block_later_tokens(admin, system):
    card = draft(admin)
    payload = card["content"]
    payload["dialogue"][0]["english"] = "coffee " + " ".join(["word"] * 34) + " last"
    payload["vocabulary"][0]["source"] = {
        "line_id": "line-1",
        "start": 0,
        "end": 6,
        "quote": "coffee",
    }
    # A blocked controlled reading must never silently fall back to its spelling.
    payload["vocabulary"][0]["pronunciation_text"] = "<invalid>"
    response = admin.put(
        f"/api/admin/v1/cards/{card['id']}", headers=key(), json={"revision": 1, "content": payload}
    )
    assert response.status_code == 200, response.text
    publish(admin, response.json())
    first = jobs(system, "pronunciation.prewarm")[0]
    run(system, first.id)
    assert len(jobs(system, "pronunciation.prewarm")) == 2
    with system["sessions"]() as db:
        assert {c.reading for c in db.scalars(select(Pronunciation))} == {"word"}
    second = next(row for row in jobs(system, "pronunciation.prewarm") if row.id != first.id)
    run(system, second.id)
    with system["sessions"]() as db:
        assert {c.reading for c in db.scalars(select(Pronunciation))} == {"word", "last"}


def test_offline_aggregate_and_child_skip_without_spending_budget(admin, system):
    card = draft(admin)
    publish(admin, card)
    warm = jobs(system, "pronunciation.prewarm")[0]
    run(system, warm.id)
    children = jobs(system, "tts.prewarm")
    response = admin.post(
        f"/api/admin/v1/cards/{card['id']}/offline", headers=key(), json={"revision": 1}
    )
    assert response.status_code == 200, response.text
    for child in children:
        run(system, child.id)
    from juya_api.content_models import SettingCounter

    with system["sessions"]() as db:
        assert not db.scalars(
            select(SettingCounter).where(SettingCounter.name.like("tts:2%"))
        ).all()
        assert all(db.get(Job, c.id).result.get("skipped") for c in children)


@pytest.mark.usefixtures("legacy_learning_features")
def test_running_warmup_is_shared_and_foreground_observes_finished_audio(admin, mini, system):
    from .test_learning_access import change, user_id

    change(admin, user_id(mini), "grant")
    card = draft(admin)
    version = publish(admin, card)["current_version_id"]
    run(system, jobs(system, "pronunciation.prewarm")[0].id)
    from juya_api.jobs import finish
    from juya_api.pronunciation import configuration, prepare
    from juya_api.security import fingerprint

    cache_key = fingerprint(
        {
            "spelling": "coffee",
            "reading": "coffee",
            "configuration": configuration(system["settings"]),
        }
    )
    with system["sessions"]() as db:
        child = db.get(Pronunciation, cache_key).job_id
    lease = claim(
        system["sessions"],
        child,
        system["time"][0].replace(tzinfo=None),
        settings=system["settings"],
    )
    ref = {"version_id": version, "line_id": "line-1", "word": "coffee", "start": 11, "end": 17}
    path = f"/api/mini/v1/cards/{card['id']}/dictionary/pronunciation"
    response = mini.post(path, headers=key(), json=ref)
    assert response.status_code == 200, response.text
    assert response.json()["job_id"] == child

    class Provider:
        def synthesize(self, *_):
            return recording()

    result, apply = prepare(
        system["settings"],
        system["sessions"],
        lease,
        system["time"][0].replace(tzinfo=None),
        Provider(),
    )
    assert finish(
        system["sessions"],
        child,
        lease["lease"],
        system["time"][0].replace(tzinfo=None),
        result,
        apply=apply,
    )
    response = mini.get(path, params=ref)
    assert response.json()["state"] == "ready", response.text
    assert mini.get(response.json()["url"]).status_code == 200


def test_backfill_is_read_only_by_default_and_execute_requires_explicit_local_published_cards(
    admin, system
):
    import pytest

    from juya_api.pronunciation_backfill import backfill

    card = draft(admin)
    version = publish(admin, card)["current_version_id"]
    settings = system["settings"]
    settings.tts_codec = "wav"
    original_ids = {row.id for row in jobs(system, "pronunciation.prewarm")}
    before = len(original_ids)
    report = backfill(
        settings, system["sessions"], [card["id"]], system["time"][0].replace(tzinfo=None)
    )
    assert report == [
        {
            "card_id": card["id"],
            "version_id": version,
            "enqueued": False,
            "word_count": 5,
            "ready_count": 0,
            "processing_count": 0,
            "to_generate_count": 5,
            "skipped_reference_count": 0,
        }
    ]
    assert len(jobs(system, "pronunciation.prewarm")) == before
    with pytest.raises(ValueError, match="local"):
        backfill(
            settings,
            system["sessions"],
            [card["id"]],
            system["time"][0].replace(tzinfo=None),
            execute=True,
        )
    settings.environment = "local"
    with pytest.raises(ValueError, match="explicit"):
        backfill(
            settings, system["sessions"], [], system["time"][0].replace(tzinfo=None), execute=True
        )
    report = backfill(
        settings,
        system["sessions"],
        [card["id"]],
        system["time"][0].replace(tzinfo=None),
        execute=True,
    )
    assert report[0]["enqueued"] is True
    assert len(jobs(system, "pronunciation.prewarm")) == before + 1
    backfill(
        settings,
        system["sessions"],
        [card["id"]],
        system["time"][0].replace(tzinfo=None),
        execute=True,
    )
    assert len(jobs(system, "pronunciation.prewarm")) == before + 1

    accepted = next(
        row.id for row in jobs(system, "pronunciation.prewarm") if row.id not in original_ids
    )
    run(system, accepted)
    with system["sessions"]() as db:
        assert db.get(Job, accepted).state == "succeeded"
    backfill(
        settings,
        system["sessions"],
        [card["id"]],
        system["time"][0].replace(tzinfo=None),
        execute=True,
    )
    with system["sessions"]() as db:
        assert db.get(Job, accepted).state == "queued"


def test_aggregate_batches_dispatch_after_interactive_work(system):
    now = system["time"][0]
    with system["sessions"].begin() as db:
        enqueue(
            db,
            "pronunciation.prewarm",
            "admin",
            "actor",
            {},
            now - timedelta(seconds=1),
            settings=system["settings"],
        )
        interactive = enqueue(
            db, "tts.synthesize", "admin", "actor", {}, now, settings=system["settings"]
        ).id
    sent = []
    assert dispatch(system["sessions"], now, sent.append, role="admin", limit=1) == 1
    assert sent == [interactive]


def test_prewarm_attempts_keep_budget_and_failed_cache_cooldown(admin, system):
    from juya_api.errors import DomainError
    from juya_api.models import Administrator
    from juya_api.pronunciation import configuration, request
    from juya_api.security import fingerprint

    card = draft(admin)
    publish(admin, card)
    run(system, jobs(system, "pronunciation.prewarm")[0].id)
    settings = system["settings"]
    settings.tts_daily_budget = 1
    calls = []

    class Provider:
        def synthesize(self, text, *_):
            calls.append(text)
            raise DomainError(503, "tts_temporary", "temporary")

    with system["sessions"]() as db:
        cache_key = fingerprint(
            {"spelling": "coffee", "reading": "coffee", "configuration": configuration(settings)}
        )
        child = db.get(Pronunciation, cache_key).job_id
    run(system, child, Provider())
    system["time"][0] += timedelta(seconds=11)
    run(system, child, Provider())
    assert calls == ["coffee"]
    import pytest

    now = system["time"][0].replace(tzinfo=None)
    with pytest.raises(DomainError, match="tts_cooldown"), system["sessions"].begin() as db:
        actor = db.scalar(select(Administrator))
        request(
            db,
            settings,
            actor,
            "admin",
            {"english": "coffee"},
            "coffee",
            configuration(settings),
            cache_key,
            now,
        )
    with system["sessions"]() as db:
        assert db.get(Job, child).error_code == "tts_budget_exceeded"


def test_republish_same_version_restarts_skipped_aggregate(admin, system):
    card = draft(admin)
    version = publish(admin, card)["current_version_id"]
    aggregate = jobs(system, "pronunciation.prewarm")[0]
    admin.post(f"/api/admin/v1/cards/{card['id']}/offline", headers=key(), json={"revision": 1})
    run(system, aggregate.id)
    with system["sessions"]() as db:
        assert db.get(Job, aggregate.id).result["skipped"]
    current = admin.get(f"/api/admin/v1/cards/{card['id']}").json()
    assert publish(admin, current)["current_version_id"] == version
    run(system, aggregate.id)
    assert jobs(system, "tts.prewarm")


def test_unconfigured_prewarm_does_not_spend_provider_attempt_budget(admin, system):
    from juya_api.content_models import SettingCounter

    card = draft(admin)
    publish(admin, card)
    run(system, jobs(system, "pronunciation.prewarm")[0].id)
    for child in jobs(system, "tts.prewarm"):
        run(system, child.id)
    with system["sessions"]() as db:
        assert not db.scalars(
            select(SettingCounter).where(SettingCounter.name.like("tts:2%"))
        ).all()
        assert all(
            row.error_code == "tts_unconfigured"
            for row in db.scalars(select(Job).where(Job.kind == "tts.prewarm"))
        )


def test_real_mysql_concurrent_dispatch_reserves_one_global_prewarm_slot(system):
    import pytest

    if system["engine"].dialect.name != "mysql":
        pytest.skip("real MySQL admission locking")
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    now = system["time"][0].replace(tzinfo=None)
    with system["sessions"].begin() as db:
        warm = [
            enqueue(db, "tts.prewarm", "mini", "actor", {}, now, settings=system["settings"]).id
            for _ in range(4)
        ]
    barrier = Barrier(4)
    sent = []

    def attempt(_):
        barrier.wait()
        return dispatch(system["sessions"], now, sent.append, role="mini")

    with ThreadPoolExecutor(max_workers=4) as pool:
        counts = list(pool.map(attempt, range(4)))
    assert sum(counts) == 1
    assert len(sent) == 1 and sent[0] in warm
    assert dispatch(system["sessions"], now + timedelta(seconds=31), sent.append, role="mini") == 1
    assert sent[0] == sent[1]
    with system["sessions"]() as db:
        assert sum(bool((row.result or {}).get("admitted")) for row in db.scalars(select(Job))) == 1


@pytest.mark.usefixtures("legacy_learning_features")
def test_real_mysql_foreground_promotion_races_claim_without_duplicate_synthesis(
    admin, mini, system
):
    import pytest

    if system["engine"].dialect.name != "mysql":
        pytest.skip("real MySQL actor/job/cache lock ordering")
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from juya_api.jobs import finish
    from juya_api.pronunciation import prepare

    from .test_learning_access import change, user_id

    change(admin, user_id(mini), "grant")
    card = draft(admin)
    version = publish(admin, card)["current_version_id"]
    run(system, jobs(system, "pronunciation.prewarm")[0].id)
    with system["sessions"]() as db:
        child = db.scalar(select(Pronunciation).where(Pronunciation.reading == "coffee")).job_id
    now = system["time"][0].replace(tzinfo=None)
    barrier = Barrier(2)
    ref = {"version_id": version, "line_id": "line-1", "word": "coffee", "start": 11, "end": 17}
    path = f"/api/mini/v1/cards/{card['id']}/dictionary/pronunciation"

    def foreground():
        barrier.wait()
        return mini.post(path, headers=key(), json=ref)

    def worker():
        barrier.wait()
        return claim(system["sessions"], child, now, settings=system["settings"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        front = pool.submit(foreground)
        back = pool.submit(worker)
        response, lease = front.result(timeout=15), back.result(timeout=15)
    assert response.status_code == 200, response.text
    calls = []

    class Provider:
        def synthesize(self, text, *_):
            calls.append(text)
            return recording()

    if lease:
        assert response.json()["job_id"] == child
        result, apply = prepare(system["settings"], system["sessions"], lease, now, Provider())
        assert finish(system["sessions"], child, lease["lease"], now, result, apply=apply)
    else:
        assert response.json()["job_id"] != child
        run(system, response.json()["job_id"], Provider())
    assert calls == ["coffee"]
    assert mini.get(path, params=ref).json()["state"] == "ready"


@pytest.mark.usefixtures("legacy_learning_features")
def test_real_mysql_running_finish_and_foreground_share_one_cache(admin, mini, system):
    import pytest

    if system["engine"].dialect.name != "mysql":
        pytest.skip("real MySQL finish/promotion lock ordering")
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from juya_api.jobs import finish
    from juya_api.pronunciation import prepare

    from .test_learning_access import change, user_id

    change(admin, user_id(mini), "grant")
    card = draft(admin)
    version = publish(admin, card)["current_version_id"]
    run(system, jobs(system, "pronunciation.prewarm")[0].id)
    with system["sessions"]() as db:
        child = db.scalar(select(Pronunciation).where(Pronunciation.reading == "coffee")).job_id
    now = system["time"][0].replace(tzinfo=None)
    lease = claim(system["sessions"], child, now, settings=system["settings"])

    class Provider:
        def synthesize(self, *_):
            return recording()

    result, apply = prepare(system["settings"], system["sessions"], lease, now, Provider())
    barrier = Barrier(2)
    ref = {"version_id": version, "line_id": "line-1", "word": "coffee", "start": 11, "end": 17}
    path = f"/api/mini/v1/cards/{card['id']}/dictionary/pronunciation"

    def foreground():
        barrier.wait()
        return mini.post(path, headers=key(), json=ref)

    def complete():
        barrier.wait()
        return finish(system["sessions"], child, lease["lease"], now, result, apply=apply)

    with ThreadPoolExecutor(max_workers=2) as pool:
        front = pool.submit(foreground)
        back = pool.submit(complete)
        response, completed = front.result(timeout=15), back.result(timeout=15)
    assert completed and response.status_code == 200, response.text
    assert response.json()["job_id"] == child
    assert mini.get(path, params=ref).json()["state"] == "ready"
    assert len(jobs(system, "tts.synthesize")) == 0


def test_body_references_skips_only_tokens_exceeding_the_controlled_word_limit():
    from juya_api.dictionary import body_references

    for length in (300, 301):
        word = "x" * length
        references = body_references(
            {"dialogue": [{"id": "line", "english": f"car {word} police"}]}, "version"
        )
        assert [ref.word for ref in references] == (
            ["car", word, "police"] if length == 300 else ["car", "police"]
        )
        assert references[-1].start == 5 + length
        assert references[-1].end == 11 + length


def test_running_prewarm_cannot_publish_audio_after_publication_is_revoked(admin, system):
    from juya_api.jobs import finish
    from juya_api.pronunciation import prepare

    card = draft(admin)
    publish(admin, card)
    run(system, jobs(system, "pronunciation.prewarm")[0].id)
    child = jobs(system, "tts.prewarm")[0]
    now = system["time"][0].replace(tzinfo=None)
    lease = claim(system["sessions"], child.id, now, settings=system["settings"])

    class Provider:
        def synthesize(self, *_):
            return recording()

    result, apply = prepare(system["settings"], system["sessions"], lease, now, Provider())
    response = admin.post(
        f"/api/admin/v1/cards/{card['id']}/offline", headers=key(), json={"revision": 1}
    )
    assert response.status_code == 200
    assert finish(system["sessions"], child.id, lease["lease"], now, result, apply=apply)
    with system["sessions"]() as db:
        assert db.get(Job, child.id).result.get("skipped")
        assert all(cache.media_id is None for cache in db.scalars(select(Pronunciation)))
