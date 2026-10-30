"""Administrator history previews expose only the active publication without learner writes."""

from sqlalchemy import func, select

from juya_api.learning_models import Checkin
from juya_api.listening_models import ListeningCompletion, ListeningDaily, ListeningProgress
from tests.content_helpers import key, recording
from tests.test_listening import A, M, article, policy, post, publish, topic


def test_topic_english_round_trip_preserves_legacy_updates(admin, mini):
    parent = topic(admin)
    created = post(
        admin,
        A + "/topics",
        {
            "name": "午间休息",
            "name_en": "A short break",
            "description": "保留简介",
            "category_id": parent["category_id"],
        },
    )
    assert created["name_en"] == "A short break"
    updated = admin.put(
        A + "/topics/" + created["id"],
        headers=key(),
        json={
            "name": "午间",
            "category_id": created["category_id"],
            "revision": created["revision"],
            "name_en": "A short break",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name_en"] == "A short break"
    assert updated.json()["description"] == "保留简介"
    live = publish(admin, article(admin, created["id"]))
    policy(admin, 1)
    assert mini.get(M + "/home").json()["topics"][0]["name_en"] == "A short break"
    assert mini.get(M + "/topics").json()["items"][0]["name_en"] == "A short break"
    assert live["topic_id"] == created["id"]
    assert parent["name_en"] == "A short break"


def test_admin_preview_reads_publication_and_only_its_media(admin, mini, system):
    item = article(admin)
    live = publish(admin, item)
    new_audio = admin.post(
        A + f"/articles/{item['id']}/media?kind=audio",
        headers=key(),
        files={"file": ("draft.wav", recording(), "audio/wav")},
    ).json()
    changed = {
        **item["payload"],
        "title_zh": "未发布标题",
        "body_en": "Secret draft words.",
        "audio_id": new_audio["id"],
    }
    assert (
        admin.put(
            A + "/articles/" + item["id"],
            headers=key(),
            json={
                "revision": live["revision"],
                "topic_id": item["topic_id"],
                "payload": changed,
            },
        ).status_code
        == 200
    )
    path = A + f"/articles/{item['id']}/published"
    preview = admin.get(path)
    assert preview.status_code == 200, preview.text
    assert preview.json()["payload"] == item["payload"]
    assert preview.json()["version_id"] == live["version_id"]
    assert preview.json()["word_count"] == item["word_count"]
    assert preview.json()["draft_topic_id"] is None
    assert admin.get(path + "/media/" + item["payload"]["audio_id"]).status_code == 200
    assert admin.head(path + "/media/" + item["payload"]["audio_id"]).status_code == 200
    assert admin.get(path + "/media/" + new_audio["id"]).status_code == 404
    with system["sessions"]() as db:
        for model in [Checkin, ListeningCompletion, ListeningDaily, ListeningProgress]:
            assert db.scalar(select(func.count()).select_from(model)) == 0
    # A learner bearer must never grant administrator preview access.
    admin.cookies.clear()
    assert (
        admin.get(path, headers={"Authorization": mini.headers["Authorization"]}).status_code == 401
    )
    assert admin.get(path + "/media/" + item["payload"]["audio_id"]).status_code == 401
    assert mini.get(path).status_code == 404


def test_admin_published_preview_rejects_unavailable_content(admin):
    item = article(admin)
    path = A + f"/articles/{item['id']}/published"
    assert admin.get(path).status_code == 404
    live = publish(admin, item)
    post(admin, A + f"/articles/{item['id']}/offline", {"revision": live["revision"]})
    assert admin.get(path).status_code == 404
    assert admin.get(path + "/media/" + item["payload"]["audio_id"]).status_code == 404


def test_home_continue_progress_and_duration_use_current_publication(admin, mini):
    item = publish(admin, article(admin))
    policy(admin, 1)
    summary = mini.get(M + "/topics/" + item["topic_id"] + "/articles").json()["items"][0]
    assert summary["audio_duration_seconds"] > 0
    assert summary["progress"] is None
    progress = {
        "version_id": item["version_id"],
        "reading_position": 7,
        "translation_open": True,
        "audio_position": 0.4,
        "playback_rate": 1.25,
    }
    assert (
        mini.put(
            M + "/articles/" + item["id"] + "/progress", json=progress, headers=key()
        ).status_code
        == 200
    )
    resume = mini.get(M + "/home").json()["continue_learning"]
    assert resume["progress"]["reading_position"] == 7
    assert resume["reading_paragraph"] == 1
    updated = admin.put(
        A + "/articles/" + item["id"],
        headers=key(),
        json={
            "revision": item["revision"],
            "topic_id": item["topic_id"],
            "payload": {**item["payload"], "body_en": "We rest again."},
        },
    ).json()
    publish(admin, updated)
    resume = mini.get(M + "/home").json()["continue_learning"]
    assert resume["progress"]["reading_position"] == 0
    assert resume["progress"]["updated_at"] is None
    assert resume["reading_paragraph"] is None


def test_admin_media_follows_republication_and_deleted_articles_are_unavailable(admin):
    item = publish(admin, article(admin))
    other = article(admin)
    next_audio = admin.post(
        A + f"/articles/{item['id']}/media?kind=audio",
        headers=key(),
        files={"file": ("next.wav", recording(), "audio/wav")},
    ).json()
    changed = admin.put(
        A + "/articles/" + item["id"],
        headers=key(),
        json={
            "revision": item["revision"],
            "topic_id": item["topic_id"],
            "payload": {
                **item["payload"],
                "title_en": "Updated publication",
                "audio_id": next_audio["id"],
            },
        },
    ).json()
    live = publish(admin, changed)
    path = A + "/articles/" + item["id"] + "/published"
    assert admin.get(path).json()["version_id"] == live["version_id"]
    assert admin.get(path + "/media/" + next_audio["id"]).status_code == 200
    assert admin.get(path + "/media/" + item["payload"]["audio_id"]).status_code == 404
    assert admin.get(path + "/media/" + other["payload"]["audio_id"]).status_code == 404
    post(admin, A + "/articles/" + item["id"] + "/delete", {"revision": live["revision"]})
    assert admin.get(path).status_code == 410
    assert admin.get(path + "/media/" + item["payload"]["audio_id"]).status_code == 410


def test_continue_paragraph_uses_original_codepoints_and_nonempty_crlf_lines(admin, mini):
    item = article(admin)
    body = "First 🌱 line.\r\n\r\nSecond line.\rThird line."
    changed = admin.put(
        A + "/articles/" + item["id"],
        headers=key(),
        json={
            "revision": item["revision"],
            "topic_id": item["topic_id"],
            "payload": {**item["payload"], "body_en": body},
        },
    ).json()
    live = publish(admin, changed)
    policy(admin, 1)
    for word, paragraph in [("First", 1), ("Second", 2), ("Third", 3)]:
        assert (
            mini.put(
                M + "/articles/" + item["id"] + "/progress",
                headers=key(),
                json={
                    "version_id": live["version_id"],
                    "reading_position": body.index(word),
                    "translation_open": False,
                    "audio_position": 0,
                    "playback_rate": 1,
                },
            ).status_code
            == 200
        )
        resume = mini.get(M + "/home").json()["continue_learning"]
        assert resume["reading_paragraph"] == paragraph
        assert resume["progress"]["reading_position"] == body.index(word)
