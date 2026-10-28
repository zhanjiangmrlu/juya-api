"""Authorization, stable queue, cloud task leases and shared learning invariants."""

from tests.content_helpers import key, picture
from tests.test_listening import A, M, article, policy, post, publish, topic


def test_frozen_queue_survives_admin_reorder(admin, mini):
    t = topic(admin)
    rows = [publish(admin, article(admin, t["id"], str(n))) for n in range(3)]
    policy(admin, 3)
    token = mini.get(M + f"/articles/{rows[0]['id']}").json()["queue_token"]
    order = admin.get(A + "/order", params={"scope": "topic", "topic_id": t["id"]}).json()
    changed = admin.put(
        A + "/order",
        headers=key(),
        json={
            "scope": "topic",
            "topic_id": t["id"],
            "revision": order["revision"],
            "article_ids": [r["id"] for r in reversed(rows)],
        },
    )
    assert changed.status_code == 200
    result = mini.get(M + f"/articles/{rows[0]['id']}/next", params={"queue_token": token}).json()
    assert result["article"]["id"] == rows[1]["id"]


def test_media_ticket_and_original_recheck_current_access(admin, mini, system):
    row = publish(admin, article(admin))
    policy(admin, 1)
    medium = row["payload"]["audio_id"]
    ticket = post(
        mini,
        M + f"/articles/{row['id']}/media-ticket",
        {"version_id": row["version_id"], "media_id": medium},
    )
    assert mini.get(ticket["url"], headers={"Range": "bytes=0-15"}).status_code == 206
    policy(admin, 0)
    assert mini.get(ticket["url"]).status_code == 403
    assert (
        mini.get(
            M + f"/articles/{row['id']}/media/{medium}", params={"version_id": row["version_id"]}
        ).status_code
        == 403
    )


def test_restricted_safe_thumbnail_does_not_unlock_original(admin, mini):
    row = article(admin)
    image = admin.post(
        A + f"/articles/{row['id']}/media?kind=image",
        headers=key(),
        files={"file": ("pic.png", picture(), "image/png")},
    ).json()
    updated = admin.put(
        A + f"/articles/{row['id']}",
        headers=key(),
        json={
            "revision": row["revision"],
            "topic_id": row["topic_id"],
            "payload": {**row["payload"], "image_id": image["id"]},
        },
    ).json()
    row = publish(admin, updated)
    policy(admin, 0)
    summary = mini.get(M + f"/articles/{row['id']}/summary").json()
    assert summary["access"]["can_learn"] is False
    assert mini.get(summary["thumbnail_url"]).status_code == 200
    assert (
        mini.get(
            M + f"/articles/{row['id']}/media/{image['id']}",
            params={"version_id": row["version_id"]},
        ).status_code
        == 403
    )


def test_failed_batch_delete_preserves_success_and_cannot_resurrect(admin, mini):
    first, second = [publish(admin, article(admin)) for _ in range(2)]
    result = post(
        admin,
        A + "/articles/batch-delete",
        {
            "items": [
                {"id": first["id"], "revision": first["revision"]},
                {"id": second["id"], "revision": second["revision"] - 1},
            ]
        },
    )
    assert [r["status"] for r in result["items"]] == ["success", "failed"]
    assert admin.get(A + f"/articles/{second['id']}").json()["status"] == "published"
    assert (
        admin.put(
            A + f"/articles/{first['id']}",
            headers=key(),
            json={
                "revision": first["revision"],
                "topic_id": first["topic_id"],
                "payload": first["payload"],
            },
        ).status_code
        == 410
    )


def test_shared_scene_and_article_completion_only_one_daily_checkin(admin, mini):
    from tests.content_helpers import draft
    from tests.content_helpers import publish as publish_scene

    scene = publish_scene(admin, draft(admin))
    row = publish(admin, article(admin))
    policy(admin, 1)
    result = post(mini, M + f"/articles/{row['id']}/complete", {"version_id": row["version_id"]})
    scene_result = post(
        mini,
        f"/api/mini/v1/cards/{scene['id']}/complete",
        {"version_id": scene["current_version_id"]},
    )
    assert result["first_checkin_today"] is True
    assert scene_result["first_checkin_today"] is False
    assert scene_result["statistics"]["completed_cards"] == 1
    assert scene_result["statistics"]["completed_articles"] == 1
    assert scene_result["statistics"]["total_checkin_days"] == 1
    assert mini.get("/api/mini/v1/me/checkins").json()["items"][0]["article_count"] == 1


class Recognizer:
    def __init__(self, words):
        self.words = words
        self.submits = 0
        self.polls = 0

    def submit(self, audio):
        assert len(audio) > 0
        self.submits += 1
        return "accepted-task"

    def poll(self, task_id):
        assert task_id == "accepted-task"
        self.polls += 1
        return None if self.polls == 1 else self.words


def recognized(body):
    from juya_api.listening_timeline import body_tokens

    tokens = body_tokens(body)
    return [
        {"word": m.group(), "start_ms": n * 100, "end_ms": n * 100 + 80}
        for n, m in enumerate(tokens)
    ]


def test_persistent_asr_task_resumes_without_resubmit_and_review_is_optional(admin, mini, system):
    from juya_api.listening_models import ListeningJob
    from juya_api.listening_timeline import run_timeline_job

    row = article(admin)
    provider = Recognizer(recognized(row["payload"]["body_en"]))
    job_id = row["timeline"]["job_id"]
    run_timeline_job(system["settings"], system["sessions"], job_id, provider=provider)
    with system["sessions"]() as db:
        assert db.get(ListeningJob, job_id).provider_task_id == "accepted-task"
    run_timeline_job(system["settings"], system["sessions"], job_id, provider=provider)
    assert provider.submits == 1
    row = admin.get(A + f"/articles/{row['id']}").json()
    assert row["timeline"]["state"] == "ready"
    assert row["timeline"]["reviewed_at"] is None
    row = publish(admin, row)
    policy(admin, 1)
    detail = mini.get(M + f"/articles/{row['id']}").json()
    assert detail["timeline"]["state"] == "ready"
    assert mini.get(M + "/statistics").json()["completed_articles"] == 0
    post(admin, A + f"/articles/{row['id']}/timeline/review", {"revision": row["revision"]})
    assert mini.get(M + "/statistics").json()["total_checkin_days"] == 0


def test_deleted_article_task_does_not_apply_late_result(admin, system):
    from juya_api.listening_models import ListeningJob
    from juya_api.listening_timeline import run_timeline_job

    row = article(admin)
    post(admin, A + f"/articles/{row['id']}/delete", {"revision": row["revision"]})
    provider = Recognizer(recognized(row["payload"]["body_en"]))
    run_timeline_job(
        system["settings"], system["sessions"], row["timeline"]["job_id"], provider=provider
    )
    assert provider.submits == 0
    with system["sessions"]() as db:
        assert db.get(ListeningJob, row["timeline"]["job_id"]).state == "cancelled"


def test_default_alignment_rejects_one_missing_body_word():
    import pytest

    from juya_api.errors import DomainError
    from juya_api.listening_timeline import align_words

    words = recognized("One two three four five six seven eight nine ten.")
    with pytest.raises(DomainError):
        align_words("One two three four five six seven eight nine ten.", words[:-1], 2000)


def test_uploaded_ready_timeline_does_not_requeue_on_same_draft_save(admin, system):
    from sqlalchemy import func, select

    from juya_api.listening_models import ListeningJob
    from juya_api.listening_timeline import body_tokens

    row = article(admin)
    words = [
        {
            "start": token.start(),
            "end": token.end(),
            "start_ms": n * 100,
            "end_ms": n * 100 + 80,
            "sentence_id": "0",
        }
        for n, token in enumerate(body_tokens(row["payload"]["body_en"]))
    ]
    result = admin.put(
        A + f"/articles/{row['id']}/timeline",
        headers=key(),
        json={
            "revision": row["revision"],
            "input_hash": row["timeline"]["input_hash"],
            "words": words,
        },
    )
    assert result.status_code == 200, result.text
    assert (
        admin.put(
            A + f"/articles/{row['id']}",
            headers=key(),
            json={
                "revision": row["revision"],
                "topic_id": row["topic_id"],
                "payload": row["payload"],
            },
        ).status_code
        == 200
    )
    with system["sessions"]() as db:
        assert db.scalar(select(func.count()).select_from(ListeningJob)) == 1


def test_deleted_imported_article_has_no_active_candidate_reference(admin, system):
    from juya_api.listening_models import ListeningJob
    from juya_api.listening_timeline import run_timeline_job
    from tests.test_listening_imports import assign, package, upload

    t = topic(admin)
    batch = upload(admin, post(admin, A + "/imports", {"mode": "zip"}), package())
    cid = batch["candidates"][0]["id"]
    batch = assign(admin, batch, cid, t["id"])
    preview = post(
        admin,
        A + f"/imports/{batch['id']}/preview",
        {"revision": batch["revision"], "candidate_ids": [cid]},
    )
    result = post(
        admin, A + f"/imports/{batch['id']}/save", {"preview_token": preview["preview_token"]}
    )
    aid = result["items"][0]["article_id"]
    row = admin.get(A + "/articles/" + aid).json()
    post(admin, A + f"/articles/{aid}/delete", {"revision": row["revision"]})
    provider = Recognizer(recognized(row["payload"]["body_en"]))
    run_timeline_job(
        system["settings"], system["sessions"], row["timeline"]["job_id"], provider=provider
    )
    assert provider.submits == 0
    with system["sessions"]() as db:
        assert db.get(ListeningJob, row["timeline"]["job_id"]).state == "cancelled"


def test_confirmed_context_lemma_and_exact_position_override_dictionary(admin, mini, system):
    from datetime import date

    from sqlalchemy import select

    from juya_api.access_models import LearningAuthorization
    from juya_api.models import User

    row = article(admin)
    payload = {
        **row["payload"],
        "body_en": "Birds fly. Birds rest.",
        "word_meanings": [
            {
                "start": 0,
                "end": 5,
                "word": "Birds",
                "lemma": "bird",
                "phonetic": "/bɜːdz/",
                "chinese": "鸟类",
            }
        ],
    }
    row = admin.put(
        A + f"/articles/{row['id']}",
        headers=key(),
        json={"revision": row["revision"], "topic_id": row["topic_id"], "payload": payload},
    ).json()
    row = publish(admin, row)
    policy(admin, 0)
    with system["sessions"].begin() as db:
        user = db.scalar(select(User))
        db.add(
            LearningAuthorization(
                user_id=user.id,
                starts_on=date(2026, 10, 1),
                expires_on=date(2026, 12, 1),
                revision=1,
            )
        )
    result = mini.get(
        M + f"/articles/{row['id']}/dictionary",
        params={"version_id": row["version_id"], "start": 0, "end": 5},
    )
    assert result.status_code == 200, result.text
    assert result.json()["source"] == "context"
    assert result.json()["lemma"] == "bird"
    assert result.json()["definitions"][0]["meaning"] == "鸟类"
    # Second occurrence has no confirmed context and cannot borrow the first meaning.
    assert (
        mini.get(
            M + f"/articles/{row['id']}/dictionary",
            params={"version_id": row["version_id"], "start": 11, "end": 16},
        ).status_code
        == 503
    )


def test_admin_category_filter_and_uploaded_unsaved_media_preview(admin):
    first = article(admin)
    second = article(admin)
    category = next(
        t for t in admin.get(A + "/topics").json()["items"] if t["id"] == first["topic_id"]
    )["category_id"]
    result = admin.get(A + "/articles", params={"category_id": category}).json()
    assert [r["id"] for r in result["items"]] == [first["id"]]
    uploaded = admin.post(
        A + f"/articles/{first['id']}/media?kind=image",
        headers=key(),
        files={"file": ("pic.png", picture(), "image/png")},
    ).json()
    assert admin.get(A + f"/articles/{first['id']}/media/{uploaded['id']}").status_code == 200
    assert admin.get(A + f"/articles/{second['id']}/media/{uploaded['id']}").status_code == 404


def test_provider_known_permission_denial_is_not_unknown_submission():
    from types import SimpleNamespace

    import pytest
    from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException

    from juya_api.errors import DomainError
    from juya_api.listening_timeline import TencentAlignment

    class API:
        def call_json(self, action, payload):
            raise TencentCloudSDKException(
                "AuthFailure.UnauthorizedOperation", "private provider detail"
            )

    gateway = TencentAlignment.__new__(TencentAlignment)
    gateway.client = API()
    gateway.settings = SimpleNamespace(asr_engine="16k_en")
    with pytest.raises(DomainError) as error:
        gateway.submit(b"valid-small-input")
    assert error.value.code == "asr_permission_denied"
    assert "private" not in str(error.value)


def test_worker_crash_during_unknown_submit_never_blindly_resubmits(admin, system):
    from datetime import datetime, timedelta

    from juya_api.listening_models import ListeningJob, ListeningTimeline
    from juya_api.listening_timeline import run_timeline_job

    row = article(admin)
    job_id = row["timeline"]["job_id"]
    with system["sessions"].begin() as db:
        job = db.get(ListeningJob, job_id)
        job.state, job.attempts = "processing", 1
        job.lease_until = datetime(2026, 10, 1) - timedelta(minutes=1)
    provider = Recognizer(recognized(row["payload"]["body_en"]))
    run_timeline_job(system["settings"], system["sessions"], job_id, provider=provider)
    assert provider.submits == 0
    with system["sessions"]() as db:
        timeline = db.get(ListeningTimeline, row["timeline"]["input_hash"])
        assert timeline.state == "needs_attention"
        assert timeline.error_code == "asr_submission_unknown"


def test_sorting_invalidates_old_edit_confirmation_without_changing_content_version(admin):
    t = topic(admin)
    rows = [publish(admin, article(admin, t["id"], str(n))) for n in range(2)]
    first = rows[0]
    order = admin.get(A + "/order", params={"scope": "topic", "topic_id": t["id"]}).json()
    assert (
        admin.put(
            A + "/order",
            headers=key(),
            json={
                "scope": "topic",
                "topic_id": t["id"],
                "revision": order["revision"],
                "article_ids": [r["id"] for r in reversed(rows)],
            },
        ).status_code
        == 200
    )
    response = admin.put(
        A + f"/articles/{first['id']}",
        headers=key(),
        json={"revision": first["revision"], "topic_id": t["id"], "payload": first["payload"]},
    )
    assert response.status_code == 409
    assert admin.get(A + f"/articles/{first['id']}").json()["version_id"] == first["version_id"]


def test_editing_published_topic_is_draft_only_until_explicit_publication(admin, mini):
    old_topic, new_topic = topic(admin), topic(admin)
    first = publish(admin, article(admin, old_topic["id"], "first"))
    following = publish(admin, article(admin, old_topic["id"], "following"))
    policy(admin, 2)
    changed = admin.put(
        A + f"/articles/{first['id']}",
        headers=key(),
        json={
            "revision": first["revision"],
            "topic_id": new_topic["id"],
            "payload": first["payload"],
        },
    )
    assert changed.status_code == 200
    changed = changed.json()
    assert changed["topic_id"] == new_topic["id"]
    assert mini.get(M + f"/articles/{first['id']}").json()["topic_id"] == old_topic["id"]
    assert mini.get(M + f"/topics/{old_topic['id']}/articles").json()["total"] == 2
    assert mini.get(M + f"/topics/{new_topic['id']}/articles").json()["total"] == 0
    assert mini.get(M + f"/articles/{first['id']}/next").json()["article"]["id"] == following["id"]
    publish(admin, changed)
    assert mini.get(M + f"/articles/{first['id']}").json()["topic_id"] == new_topic["id"]
    assert mini.get(M + f"/topics/{old_topic['id']}/articles").json()["total"] == 1
    assert mini.get(M + f"/topics/{new_topic['id']}/articles").json()["total"] == 1


def test_category_english_and_topic_description_survive_older_update_requests(admin):
    category = post(
        admin, A + "/categories", {"name": "日常", "name_en": "Everyday", "sort_order": 0}
    )
    assert category["name_en"] == "Everyday"
    updated = admin.put(
        A + f"/categories/{category['id']}",
        headers=key(),
        json={"name": "日常生活", "sort_order": 1, "revision": category["revision"]},
    )
    assert updated.status_code == 200
    assert updated.json()["name_en"] == "Everyday"
    row = post(
        admin,
        A + "/topics",
        {"name": "午间", "category_id": category["id"], "description": "用几分钟休息学习。"},
    )
    updated = admin.put(
        A + f"/topics/{row['id']}",
        headers=key(),
        json={
            "name": row["name"],
            "category_id": row["category_id"],
            "sort_order": 1,
            "revision": row["revision"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "用几分钟休息学习。"


def test_completion_uses_acceptance_clock_after_catalog_lock_at_midnight(
    admin, mini, system, monkeypatch
):
    from datetime import UTC, datetime

    from juya_api import listening_service

    row = publish(admin, article(admin))
    policy(admin, 1)
    system["time"][0] = datetime(2026, 10, 17, 15, 59, 59, tzinfo=UTC)
    original = listening_service.catalog_lock

    def cross_midnight(db, *, shared=False):
        result = original(db, shared=shared)
        if shared:
            system["time"][0] = datetime(2026, 10, 17, 16, 0, 0, tzinfo=UTC)
        return result

    monkeypatch.setattr(listening_service, "catalog_lock", cross_midnight)
    response = post(mini, M + f"/articles/{row['id']}/complete", {"version_id": row["version_id"]})
    assert response["date"] == "2026-10-18"


def test_authorization_expiring_during_catalog_wait_is_rechecked(admin, mini, system, monkeypatch):
    from datetime import UTC, date, datetime

    from sqlalchemy import select

    from juya_api import listening_service
    from juya_api.access_models import LearningAuthorization
    from juya_api.models import User

    row = publish(admin, article(admin))
    policy(admin, 0)
    with system["sessions"].begin() as db:
        user = db.scalar(select(User))
        db.add(
            LearningAuthorization(
                user_id=user.id,
                starts_on=date(2026, 10, 1),
                expires_on=date(2026, 10, 17),
                revision=1,
            )
        )
    system["time"][0] = datetime(2026, 10, 17, 15, 59, 59, tzinfo=UTC)
    original = listening_service.catalog_lock

    def cross_midnight(db, *, shared=False):
        result = original(db, shared=shared)
        if shared:
            system["time"][0] = datetime(2026, 10, 17, 16, 0, 0, tzinfo=UTC)
        return result

    monkeypatch.setattr(listening_service, "catalog_lock", cross_midnight)
    response = mini.post(
        M + f"/articles/{row['id']}/complete", headers=key(), json={"version_id": row["version_id"]}
    )
    assert response.status_code == 403
    assert mini.get(M + "/statistics").json()["completed_articles"] == 0


def test_free_configuration_keeps_auditable_before_and_after_results(admin, system):
    import json

    from sqlalchemy import select

    from juya_api.content_models import Operation
    from juya_api.security import decrypt

    policy(admin, 1)
    policy(admin, 0)
    with system["sessions"]() as db:
        rows = list(
            db.scalars(
                select(Operation)
                .where(Operation.action == "listening.free.save")
                .order_by(Operation.accepted_at, Operation.key_digest)
            )
        )
        facts = [json.loads(decrypt(system["settings"], row.result)) for row in rows]
        transitions = {
            (fact["audit"]["before"]["free_count"], fact["audit"]["after"]["free_count"])
            for fact in facts
        }
        assert transitions == {(None, 1), (1, 0)}
        assert all(fact["audit"]["admin_id"] and fact["audit"]["occurred_at"] for fact in facts)
