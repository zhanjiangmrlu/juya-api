"""Revision17 domain acceptance through real HTTP and SQL persistence."""

from datetime import UTC, datetime

from sqlalchemy import func, select

from tests.content_helpers import key, recording

A = "/api/admin/v1/listening"
M = "/api/mini/v1/listening"


def post(client, path, body):
    response = client.post(path, json=body, headers=key())
    assert response.status_code in {200, 201}, response.text
    return response.json()


def topic(admin):
    category = post(admin, A + "/categories", {"name": "日常", "sort_order": 0})
    return post(admin, A + "/topics", {"name": "午间", "category_id": category["id"]})


def article(admin, topic_id=None, title="午间休息"):
    item = post(admin, A + "/articles", {"topic_id": topic_id or topic(admin)["id"], "payload": {}})
    audio = admin.post(
        A + f"/articles/{item['id']}/media?kind=audio",
        headers=key(),
        files={"file": ("complete.wav", recording(), "audio/wav")},
    )
    assert audio.status_code == 200, audio.text
    payload = {
        "title_zh": title,
        "title_en": "A short break",
        "tags": ["生活"],
        "body_en": "We don't need a well-known plan.\nWe rest.",
        "translation_zh": "我们不需要计划。\n我们休息。",
        "expressions": [
            {"english": "take a break", "chinese": "休息", "example": "Take a short break."}
        ]
        * 5,
        "audio_id": audio.json()["id"],
        "image_id": None,
        "word_meanings": [],
    }
    response = admin.put(
        A + f"/articles/{item['id']}",
        headers=key(),
        json={"revision": item["revision"], "topic_id": item["topic_id"], "payload": payload},
    )
    assert response.status_code == 200, response.text
    return response.json()


def publish(admin, item):
    preview = post(admin, A + f"/articles/{item['id']}/preview", {"revision": item["revision"]})
    return post(
        admin,
        A + f"/articles/{item['id']}/publish",
        {"revision": item["revision"], "preview_token": preview["preview_token"]},
    )


def policy(admin, count):
    preview = post(admin, A + "/free-policy/preview", {"free_count": count})
    response = admin.put(
        A + "/free-policy", headers=key(), json={"preview_token": preview["preview_token"]}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_draft_publish_snapshot_and_unconfigured_access(admin, mini):
    item = article(admin)
    assert item["word_count"] == 8  # apostrophe/hyphen each remain one token
    assert mini.get(M + "/home").json()["topics"] == []
    live = publish(admin, item)
    assert mini.get(M + f"/articles/{live['id']}").status_code == 403
    policy(admin, 1)
    detail = mini.get(M + f"/articles/{live['id']}").json()
    assert detail["payload"]["title_zh"] == item["payload"]["title_zh"]
    changed = {**item["payload"], "title_zh": "未发布改稿"}
    update = admin.put(
        A + f"/articles/{live['id']}",
        headers=key(),
        json={"revision": live["revision"], "topic_id": item["topic_id"], "payload": changed},
    )
    assert update.status_code == 200
    assert mini.get(M + f"/articles/{live['id']}").json()["payload"]["title_zh"] != "未发布改稿"
    assert (
        mini.get(
            M + f"/articles/{live['id']}/dictionary",
            params={"version_id": live["version_id"], "start": 0, "end": 2},
        ).status_code
        == 403
    )


def test_global_m_is_independent_of_topic_order_and_completion(admin, mini):
    t = topic(admin)
    first, second = [publish(admin, article(admin, t["id"], str(n))) for n in range(2)]
    policy(admin, 1)
    post(mini, M + f"/articles/{first['id']}/complete", {"version_id": first["version_id"]})
    assert mini.get(M + f"/articles/{second['id']}/summary").json()["access"]["can_learn"] is False
    order = admin.get(A + "/order?scope=topic&topic_id=" + t["id"]).json()
    result = admin.put(
        A + "/order",
        headers=key(),
        json={
            "scope": "topic",
            "topic_id": t["id"],
            "article_ids": [second["id"], first["id"]],
            "revision": order["revision"],
        },
    )
    assert result.status_code == 200, result.text
    assert mini.get(M + f"/articles/{first['id']}/summary").json()["access"]["is_free"]
    assert mini.get(M + f"/articles/{first['id']}/next").json()["ended"] is True


def test_completion_receipt_cross_midnight_shared_checkin_and_deleted_history(admin, mini, system):
    first = publish(admin, article(admin))
    policy(admin, 1)
    headers = key()
    path = M + f"/articles/{first['id']}/complete"
    body = {"version_id": first["version_id"]}
    accepted = mini.post(path, headers=headers, json=body)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["statistics"]["completed_articles"] == 1
    assert accepted.json()["statistics"]["completed_cards"] == 0
    system["time"][0] = datetime(2026, 10, 18, 0, 1, tzinfo=UTC)
    assert mini.post(path, headers=headers, json=body).json() == accepted.json()
    reviewed = post(mini, path, body)
    assert reviewed["statistics"]["completed_articles"] == 1
    assert reviewed["statistics"]["total_checkin_days"] == 2
    post(admin, A + f"/articles/{first['id']}/delete", {"revision": first["revision"]})
    assert mini.get(M + f"/articles/{first['id']}").status_code in {403, 410}
    records = mini.get(M + "/records").json()
    assert records["total"] == 1 and records["items"][0]["available"] is False
    assert mini.get(M + "/statistics").json()["completed_articles"] == 1


def test_progress_version_reset_and_stale_publish_preview(admin, mini):
    live = publish(admin, article(admin))
    policy(admin, 1)
    progress = {
        "version_id": live["version_id"],
        "reading_position": 7,
        "translation_open": True,
        "audio_position": 0.4,
        "playback_rate": 1.75,
    }
    assert (
        mini.put(M + f"/articles/{live['id']}/progress", json=progress, headers=key()).status_code
        == 200
    )
    assert mini.get(M + f"/articles/{live['id']}").json()["progress"]["translation_open"]
    preview = post(admin, A + f"/articles/{live['id']}/preview", {"revision": live["revision"]})
    updated = admin.put(
        A + f"/articles/{live['id']}",
        headers=key(),
        json={
            "revision": live["revision"],
            "topic_id": live["topic_id"],
            "payload": {**live["payload"], "body_en": "We rest again."},
        },
    ).json()
    assert (
        admin.post(
            A + f"/articles/{live['id']}/publish",
            headers=key(),
            json={"revision": updated["revision"], "preview_token": preview["preview_token"]},
        ).status_code
        == 409
    )
    publish(admin, updated)
    detail = mini.get(M + f"/articles/{live['id']}").json()
    assert detail["progress"]["audio_position"] == 0
    assert detail["progress"]["playback_rate"] == 1


def test_free_preview_stale_and_invalid_m(admin, mini):
    item = publish(admin, article(admin))
    preview = post(admin, A + "/free-policy/preview", {"free_count": 1})
    post(admin, A + f"/articles/{item['id']}/offline", {"revision": item["revision"]})
    assert (
        admin.put(
            A + "/free-policy", headers=key(), json={"preview_token": preview["preview_token"]}
        ).status_code
        == 409
    )
    for value in [-1, 1.2, "1", None, True]:
        assert (
            admin.post(
                A + "/free-policy/preview", headers=key(), json={"free_count": value}
            ).status_code
            == 422
        )


def test_timeline_job_deduplicates_and_rejects_wrong_ranges(admin, mini, system):
    from juya_api.listening_models import ListeningJob

    item = article(admin)
    with system["sessions"]() as db:
        assert db.scalar(select(func.count()).select_from(ListeningJob)) == 1
    again = admin.put(
        A + f"/articles/{item['id']}",
        headers=key(),
        json={
            "revision": item["revision"],
            "topic_id": item["topic_id"],
            "payload": item["payload"],
        },
    ).json()
    with system["sessions"]() as db:
        assert db.scalar(select(func.count()).select_from(ListeningJob)) == 1
    state = admin.get(A + f"/articles/{item['id']}/timeline").json()
    invalid = admin.put(
        A + f"/articles/{item['id']}/timeline",
        headers=key(),
        json={
            "revision": again["revision"],
            "input_hash": state["input_hash"],
            "words": [{"start": 0, "end": 2, "start_ms": 900, "end_ms": 1200, "sentence_id": "0"}],
        },
    )
    assert invalid.status_code == 422, invalid.text
    published = publish(admin, again)
    policy(admin, 1)
    assert mini.get(M + f"/articles/{published['id']}").json()["timeline"]["state"] != "ready"


def test_timeline_alignment_repeated_words_and_insufficient_match():
    from juya_api.listening_timeline import align_words

    body = "We rest. We rest."
    words = [
        {"word": "We", "start_ms": 0, "end_ms": 90},
        {"word": "rest", "start_ms": 100, "end_ms": 200},
        {"word": "We", "start_ms": 300, "end_ms": 390},
        {"word": "rest", "start_ms": 400, "end_ms": 500},
    ]
    result = align_words(body, words, 1000, minimum_coverage=0.9)
    assert [w["start"] for w in result] == [0, 3, 9, 12]
    import pytest

    from juya_api.errors import DomainError

    with pytest.raises(DomainError):
        align_words(body, words[:1], 1000, minimum_coverage=0.9)
