"""Partial recognition keeps real timestamps and can reuse an accepted cloud task."""

import pytest

from juya_api.errors import DomainError
from juya_api.listening_timeline import align_words, run_timeline_job
from tests.test_listening import A, M, article, policy, post, publish


def test_partial_match_skips_missing_and_changed_words_without_inventing_times():
    body = "We explain the argument today."
    recognized = [
        {"word": "We", "start_ms": 0, "end_ms": 100},
        {"word": "explained", "start_ms": 110, "end_ms": 300},
        {"word": "the", "start_ms": 310, "end_ms": 400},
        {"word": "today", "start_ms": 800, "end_ms": 1000},
    ]
    words = align_words(body, recognized, 1100)
    assert [(w["start"], w["end"], w["start_ms"], w["end_ms"]) for w in words] == [
        (0, 2, 0, 100),
        (11, 14, 310, 400),
        (24, 29, 800, 1000),
    ]


def test_no_matching_words_remains_unavailable():
    with pytest.raises(DomainError):
        align_words("We explain.", [{"word": "unrelated", "start_ms": 0, "end_ms": 100}], 1000)


def test_partial_match_still_rejects_overlapping_timestamps():
    with pytest.raises(DomainError) as exc:
        align_words(
            "We explain today.",
            [
                {"word": "We", "start_ms": 0, "end_ms": 300},
                {"word": "today", "start_ms": 200, "end_ms": 400},
            ],
            1000,
        )
    assert exc.value.code == "timeline_invalid"


def test_retry_alignment_failure_reuses_provider_result_without_submitting(admin, mini, system):
    from juya_api.listening_models import ListeningJob, ListeningTimeline

    row = article(admin)
    old_id = row["timeline"]["job_id"]
    with system["sessions"].begin() as db:
        job = db.get(ListeningJob, old_id)
        job.state, job.error_code, job.provider_task_id = (
            "failed",
            "timeline_coverage_low",
            "existing-task",
        )
        timeline = db.get(ListeningTimeline, job.input_hash)
        timeline.state, timeline.error_code = "needs_attention", "timeline_coverage_low"

    class ExistingResult:
        def submit(self, audio):
            pytest.fail("Reusing an existing result must not submit audio")

        def poll(self, task_id):
            assert task_id == "existing-task"
            return [{"word": "We", "start_ms": 0, "end_ms": 100}]

    retried = post(
        admin, A + f"/articles/{row['id']}/timeline/retry", {"revision": row["revision"]}
    )
    with system["sessions"]() as db:
        assert db.get(ListeningJob, retried["job_id"]).provider_task_id == "existing-task"
    run_timeline_job(
        system["settings"],
        system["sessions"],
        retried["job_id"],
        provider=ExistingResult(),
        clock=lambda: system["time"][0],
    )
    published = publish(admin, admin.get(A + f"/articles/{row['id']}").json())
    policy(admin, 1)
    detail = mini.get(M + f"/articles/{published['id']}").json()
    assert detail["timeline"]["state"] == "ready"
    assert len(detail["timeline"]["words"]) == 1


def test_retry_after_existing_result_query_failure_never_falls_back_to_new_recognition(
    admin, system
):
    from juya_api.listening_models import ListeningJob, ListeningTimeline

    row = article(admin)
    with system["sessions"].begin() as db:
        job = db.get(ListeningJob, row["timeline"]["job_id"])
        job.state, job.error_code, job.provider_task_id = (
            "failed",
            "asr_request_invalid",
            "accepted-task",
        )
        timeline = db.get(ListeningTimeline, job.input_hash)
        timeline.state, timeline.error_code = "failed", "asr_request_invalid"
    retried = post(
        admin, A + f"/articles/{row['id']}/timeline/retry", {"revision": row["revision"]}
    )
    with system["sessions"]() as db:
        assert db.get(ListeningJob, retried["job_id"]).provider_task_id == "accepted-task"


def test_expired_provider_result_is_not_queried_or_resubmitted(admin, system):
    from datetime import timedelta

    from juya_api.listening_models import ListeningJob, ListeningTimeline
    from tests.content_helpers import key

    row = article(admin)
    with system["sessions"].begin() as db:
        job = db.get(ListeningJob, row["timeline"]["job_id"])
        job.state, job.error_code, job.provider_task_id = (
            "failed",
            "timeline_coverage_low",
            "expired-task",
        )
        job.created_at = system["time"][0] - timedelta(hours=24)
        timeline = db.get(ListeningTimeline, job.input_hash)
        timeline.state, timeline.error_code = "needs_attention", "timeline_coverage_low"
    response = admin.post(
        A + f"/articles/{row['id']}/timeline/retry",
        json={"revision": row["revision"]},
        headers=key(),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "asr_result_expired"
    with system["sessions"]() as db:
        assert db.get(ListeningJob, row["timeline"]["job_id"]).state == "failed"


def test_worker_rejects_expired_result_before_any_cloud_call(admin, system):
    from datetime import timedelta

    from juya_api.listening_models import ListeningJob

    row = article(admin)
    with system["sessions"].begin() as db:
        job = db.get(ListeningJob, row["timeline"]["job_id"])
        job.provider_task_id = "expired-task"
        job.created_at = system["time"][0] - timedelta(hours=24)

    class NoCloudCalls:
        def poll(self, task_id):
            pytest.fail("Expired result must not be queried")

        def submit(self, audio):
            pytest.fail("Expired result must not be resubmitted")

    run_timeline_job(
        system["settings"],
        system["sessions"],
        row["timeline"]["job_id"],
        provider=NoCloudCalls(),
        clock=lambda: system["time"][0],
    )
    with system["sessions"]() as db:
        job = db.get(ListeningJob, row["timeline"]["job_id"])
        assert job.state == "failed"
        assert job.error_code == "asr_result_expired"
