"""Private ordered feedback, independent read cursors and durable upload/write recovery."""

import io
from concurrent.futures import ThreadPoolExecutor

import pytest
from PIL import Image
from sqlalchemy import func, select

from .content_helpers import draft, key, picture, publish

MINI = "/api/mini/v1/feedback"
ADMIN = "/api/admin/v1/feedback"


class SafeContent:
    """Substitute only the external content-safety decision for isolated test content."""

    def check_text(self, text, correlation_id):
        from juya_api.errors import DomainError

        if "blocked" in text:
            raise DomainError(422, "content_rejected", "内容未通过安全检查")

    def check_image(self, data, content_type, correlation_id):
        return None


class UnavailableContent:
    def check_text(self, *_):
        from juya_api.errors import DomainError

        raise DomainError(503, "content_safety_unavailable", "检查暂不可用")

    check_image = check_text


@pytest.fixture
def feedback(mini, admin):
    mini.app.state.feedback_safety = SafeContent()
    admin.app.state.feedback_safety = SafeContent()
    return mini, admin


def create(mini, **extra):
    response = mini.post(
        MINI,
        json={"category": "content", "text": "私人反馈原说明", "source": "profile"} | extra,
        headers=key(),
    )
    assert response.status_code == 201, response.text
    return response.json()


def supplement(mini, item, text="补充说明", **extra):
    return mini.post(
        MINI + "/" + item["id"] + "/messages", json={"text": text} | extra, headers=key()
    )


def reply(admin, item, text="管理员回复", **extra):
    return admin.post(
        ADMIN + "/" + item["id"] + "/messages", json={"text": text} | extra, headers=key()
    )


def test_feedback_replay_precedes_safety_failure_and_text_is_encrypted(feedback, system):
    mini, admin = feedback
    headers = key()
    body = {"category": "content", "text": "  私人反馈原说明  ", "source": "profile"}
    first = mini.post(MINI, json=body, headers=headers)
    assert first.status_code == 201, first.text
    item = first.json()
    assert item["events"][0]["text"] == "私人反馈原说明"
    assert item["events"][0]["id"] == item["latest_event_id"] == 1
    assert item["status"] == "pending"
    mini.app.state.feedback_safety = UnavailableContent()
    assert mini.post(MINI, json=body, headers=headers).json() == item
    changed = mini.post(MINI, json=body | {"text": "内容已改变"}, headers=headers)
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "operation_conflict"
    receipt = mini.get("/api/mini/v1/operations/" + headers["Idempotency-Key"])
    assert receipt.json()["result"] == item
    listing = mini.get(MINI).json()
    assert listing["total"] == 1 and listing["items"][0]["events"] == []
    assert admin.get(ADMIN, params={"search": "反馈原说"}).json()["total"] == 1
    from juya_api.feedback_models import Feedback, FeedbackEvent

    with system["sessions"]() as db:
        assert "私人反馈" not in db.scalar(select(Feedback)).summary_cipher
        assert "私人反馈" not in db.scalar(select(FeedbackEvent)).text_cipher


@pytest.mark.parametrize(
    "changes",
    [
        {"text": " "},
        {"text": "字" * 501},
        {"category": "other"},
        {"images": ["a", "b", "c", "d"]},
        {"images": ["a", "a"]},
        {"source": "scene"},
        {"card_id": "unexpected"},
    ],
)
def test_invalid_feedback_never_creates_a_record(feedback, changes):
    mini, admin = feedback
    response = mini.post(
        MINI,
        json={"category": "content", "text": "说明", "source": "profile"} | changes,
        headers=key(),
    )
    assert response.status_code == 422, response.text
    assert admin.get(ADMIN).json()["total"] == 0


def test_unicode_limit_is_codepoints_and_supplements_are_unlimited(feedback):
    mini, admin = feedback
    item = create(mini, text="😀" * 500)
    for status in ["processing", "needs_info", "resolved"]:
        response = reply(admin, item, status=status)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == status
    assert reply(admin, item).json()["status"] == "resolved"
    for index in range(4):
        added = supplement(mini, item, f"第{index}次补充")
        assert added.status_code == 200, added.text
        assert added.json()["status"] == "pending"
    assert supplement(mini, item, "😀" * 501).status_code == 422
    final = mini.get(MINI + "/" + item["id"]).json()
    assert [event["id"] for event in final["events"]] == list(range(1, 10))
    assert final["events"][0]["text"] == "😀" * 500
    assert admin.get(ADMIN, params={"status": "pending"}).json()["total"] == 1
    assert admin.get(ADMIN, params={"status": "resolved"}).json()["total"] == 0


def test_admin_explicit_status_requires_explanation_and_conflicts_write_nothing(feedback):
    mini, admin = feedback
    item = create(mini)
    url = ADMIN + "/" + item["id"] + "/messages"
    for body in [
        {},
        {"status": "needs_info"},
        {"status": "resolved", "text": " "},
        {"status": "pending"},
    ]:
        assert admin.post(url, json=body, headers=key()).status_code == 422
    started = admin.post(
        url, json={"status": "processing", "expected_latest_event_id": 1}, headers=key()
    )
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "processing"
    assert mini.get(MINI + "/unread").json() == {"unread": False, "count": 0}
    conflict = admin.post(
        url,
        json={"text": "过期动作", "status": "resolved", "expected_latest_event_id": 1},
        headers=key(),
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "feedback_changed"
    current = mini.get(MINI + "/" + item["id"]).json()
    assert current["latest_event_id"] == 2 and current["status"] == "processing"


def test_displayed_event_cursors_do_not_clear_other_threads_or_concurrent_events(feedback):
    mini, admin = feedback
    first, second = create(mini), create(mini)
    for item in [first, second]:
        assert reply(admin, item, status="needs_info").status_code == 200
    shown = mini.get(MINI + "/" + first["id"]).json()
    assert mini.get(MINI).status_code == 200
    assert mini.get(MINI + "/unread").json() == {"unread": True, "count": 2}
    later = reply(admin, first).json()
    headers = key()
    path = MINI + "/" + first["id"] + "/read"
    read = mini.put(path, json={"event_id": shown["latest_event_id"]}, headers=headers)
    assert read.json() == {"feedback_id": first["id"], "read_event_id": 2}
    assert mini.get(MINI + "/" + first["id"]).json()["unread"] is True
    assert admin.get(ADMIN + "/" + first["id"]).json()["unread"] is True
    assert (
        mini.put(path, json={"event_id": shown["latest_event_id"]}, headers=headers).json()
        == read.json()
    )
    assert (
        mini.put(path, json={"event_id": later["latest_event_id"]}, headers=key()).json()[
            "read_event_id"
        ]
        == 3
    )
    assert mini.put(path, json={"event_id": 1}, headers=key()).json()["read_event_id"] == 3
    assert mini.get(MINI + "/unread").json()["count"] == 1
    assert mini.put(path, json={"event_id": 999}, headers=key()).status_code == 422
    assert mini.get(MINI + "/" + first["id"]).json()["status"] == "needs_info"


def test_feedback_and_image_references_are_owned_and_admin_credentials_are_separate(feedback):
    mini, admin = feedback
    item = create(mini)
    original = mini.headers.pop("Authorization")
    assert mini.get(MINI).status_code == 401
    assert mini.get(MINI + "/" + item["id"]).status_code == 401
    mini.headers["Authorization"] = original
    login = mini.post(
        "/api/mini/v1/auth/wechat",
        headers=key(),
        json={"code": "bob:feedback", "consent": True, "consent_version": "2026-10-17"},
    )
    mini.headers["Authorization"] = "Bearer " + login.json()["access_token"]
    assert mini.get(MINI).json()["total"] == 0
    assert mini.get(MINI + "/" + item["id"]).status_code == 404
    assert supplement(mini, item).status_code == 404
    assert (
        mini.put(MINI + "/" + item["id"] + "/read", json={"event_id": 1}, headers=key()).status_code
        == 404
    )
    csrf = admin.headers.pop("X-CSRF-Token")
    assert reply(admin, item).status_code == 403
    admin.headers["X-CSRF-Token"] = csrf
    admin.cookies.clear()
    assert admin.get(ADMIN).status_code == 401
    assert reply(admin, item).status_code == 401


def test_source_uses_published_summary_and_history_survives_disable_and_delete(feedback, system):
    from juya_api.content_models import Card, CardDraft

    mini, admin = feedback
    card = publish(admin, draft(admin))
    item = create(mini, source="scene", card_id=card["id"], version_id=card["current_version_id"])
    assert item["source_available"] is True
    assert item["source_title"] == "在咖啡店点单"
    assert item["source_title_en"] == "Ordering Coffee"
    with system["sessions"].begin() as db:
        db.get(Card, card["id"]).status = "offline"
        db.get(CardDraft, card["id"]).payload = {"name": "未发布私密标题"}
    detail = mini.get(MINI + "/" + item["id"]).json()
    assert detail["source_available"] is False
    assert detail["source_unavailable_reason"] == "offline"
    assert "未发布私密" not in str(detail)
    assert supplement(mini, item).status_code == 200
    unavailable = mini.post(
        MINI,
        json={
            "category": "content",
            "text": "旧来源",
            "source": "scene",
            "card_id": card["id"],
            "version_id": card["current_version_id"],
        },
        headers=key(),
    )
    assert unavailable.status_code == 410
    with system["sessions"].begin() as db:
        db.get(Card, card["id"]).deleted_at = mini.app.state.clock()
    assert mini.get(MINI + "/" + item["id"]).json()["source_unavailable_reason"] == "deleted"


def test_image_decode_private_grants_renewal_and_one_time_binding(feedback, system):
    mini, admin = feedback
    invalid = mini.post(
        MINI + "/images",
        files={"file": ("fake.png", b"<script>x</script>", "image/png")},
        headers=key(),
    )
    assert invalid.status_code == 422
    image_headers = key()
    image_body = {"file": ("not-really.txt", picture(), "text/plain")}
    uploaded = mini.post(MINI + "/images", files=image_body, headers=image_headers)
    assert uploaded.status_code == 201, uploaded.text
    image = uploaded.json()
    assert image["state"] == "ready"
    assert admin.get(ADMIN + "/images/" + image["id"] + "/url").status_code == 404
    data = mini.get(image["url"])
    assert data.status_code == 200
    assert Image.open(io.BytesIO(data.content)).format in {"JPEG", "PNG", "WEBP"}
    assert data.headers["Cache-Control"] == "no-store"
    assert data.headers["X-Content-Type-Options"] == "nosniff"
    item = create(mini, images=[image["id"]])
    assert len(item["events"][0]["images"]) == 1
    assert supplement(mini, item, images=[image["id"]]).status_code == 422
    admin_image = admin.get(ADMIN + "/" + item["id"]).json()["events"][0]["images"][0]
    assert admin.get(admin_image["url"]).status_code == 200
    from datetime import timedelta

    system["time"][0] += timedelta(minutes=5)
    assert mini.get(image["url"]).status_code == 401
    fresh = mini.get(MINI + "/images/" + image["id"] + "/url")
    assert fresh.status_code == 200
    authorization = mini.headers.pop("Authorization")
    assert mini.get(fresh.json()["url"]).status_code == 200
    mini.headers["Authorization"] = authorization
    assert mini.post("/api/mini/v1/auth/logout", headers=key()).status_code == 200
    assert mini.get(fresh.json()["url"]).status_code == 401


def test_three_images_accept_and_four_reject_and_unbound_images_can_renew(feedback):
    mini, _ = feedback
    images = []
    for _ in range(3):
        response = mini.post(
            MINI + "/images", files={"file": ("scene.png", picture(), "image/png")}, headers=key()
        )
        assert response.status_code == 201, response.text
        images.append(response.json()["id"])
    assert mini.get(MINI + "/images/" + images[0] + "/url").status_code == 200
    item = create(mini, images=images)
    assert len(item["events"][0]["images"]) == 3
    assert supplement(mini, item, images=[*images, "another"]).status_code == 422


def test_safety_failure_never_creates_feedback_or_changes_existing_status(feedback):
    mini, admin = feedback
    item = create(mini)
    assert reply(admin, item, text="blocked", status="resolved").status_code == 422
    assert supplement(mini, item, text="blocked").status_code == 422
    mini.app.state.feedback_safety = UnavailableContent()
    assert supplement(mini, item).status_code == 503
    assert (
        mini.post(
            MINI + "/images", files={"file": ("pic.png", picture(), "image/png")}, headers=key()
        ).status_code
        == 503
    )
    final = admin.get(ADMIN + "/" + item["id"]).json()
    assert final["status"] == "pending" and final["latest_event_id"] == 1


def test_concurrent_accepted_reply_and_supplement_preserve_both_server_events(feedback, system):
    mini, admin = feedback
    item = create(mini)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [
            pool.submit(reply, admin, item, status="resolved"),
            pool.submit(supplement, mini, item),
        ]
        responses = [job.result() for job in jobs]
    assert [response.status_code for response in responses] == [200, 200]
    final = mini.get(MINI + "/" + item["id"]).json()
    assert [event["id"] for event in final["events"]] == [1, 2, 3]
    assert final["status"] == ("pending" if final["events"][-1]["actor"] == "user" else "resolved")
    from juya_api.feedback_models import FeedbackEvent

    with system["sessions"]() as db:
        assert db.scalar(select(func.count()).select_from(FeedbackEvent)) == 3


def test_metadata_is_stripped_and_large_screenshots_are_compressed(feedback):
    mini, _ = feedback
    image = Image.new("RGB", (2600, 2200), "white")
    exif = Image.Exif()
    exif[270] = "private screenshot metadata"
    output = io.BytesIO()
    image.save(output, format="JPEG", exif=exif)
    uploaded = mini.post(
        MINI + "/images",
        files={"file": ("screen.jpg", output.getvalue(), "image/jpeg")},
        headers=key(),
    )
    assert uploaded.status_code == 201, uploaded.text
    response = mini.get(uploaded.json()["url"])
    normalized = Image.open(io.BytesIO(response.content))
    assert max(normalized.size) <= 2048
    assert not normalized.getexif()
    assert b"private screenshot metadata" not in response.content


def test_readiness_rejects_schema_before_feedback_tables(system):
    from sqlalchemy import text

    from juya_api.content_models import SettingCounter

    with system["sessions"].begin() as db:
        db.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        db.execute(text("INSERT INTO alembic_version VALUES ('0014')"))
        db.merge(SettingCounter(name="schema_contract", value=1))
    assert system["mini"].get("/health/ready").status_code == 503
    assert system["admin"].get("/health/ready").status_code == 503


def test_slow_safety_uses_acceptance_clock_and_never_moves_thread_time_backwards(feedback, system):
    from datetime import timedelta

    from juya_api.content_models import Operation
    from juya_api.database import timestamp
    from juya_api.security import digest

    mini, admin = feedback
    item = create(mini)
    original = system["time"][0]
    system["time"][0] = original + timedelta(minutes=20)
    assert reply(admin, item).status_code == 200
    system["time"][0] = original + timedelta(minutes=10)

    class SlowSafety(SafeContent):
        def check_text(self, *_):
            system["time"][0] = original + timedelta(minutes=30)

    mini.app.state.feedback_safety = SlowSafety()
    headers = key()
    response = mini.post(
        MINI + "/" + item["id"] + "/messages", json={"text": "延迟检查后的补充"}, headers=headers
    )
    assert response.status_code == 200, response.text
    expected = timestamp(mini.app.state.clock())
    assert response.json()["updated_at"] == expected
    assert response.json()["events"][-1]["created_at"] == expected
    with system["sessions"]() as db:
        operation = db.get(
            Operation, ("mini:" + item["user_id"], digest(headers["Idempotency-Key"]))
        )
        assert timestamp(operation.accepted_at) == expected


def test_screenshot_order_follows_selected_reference_order(feedback):
    mini, _ = feedback
    ids = []
    for _ in range(3):
        uploaded = mini.post(
            MINI + "/images", files={"file": ("s.png", picture(), "image/png")}, headers=key()
        )
        assert uploaded.status_code == 201, uploaded.text
        ids.append(uploaded.json()["id"])
    selected = sorted(ids, reverse=True)
    item = create(mini, images=selected)
    assert [image["id"] for image in item["events"][0]["images"]] == selected


@pytest.mark.mysql
def test_real_mysql_feedback_append_and_read_watermark_order(feedback, system):
    if system["engine"].dialect.name != "mysql":
        pytest.skip("Real MySQL feedback row locking and displayed-event read watermarks")
    from threading import Barrier

    mini, admin = feedback
    item = create(mini)
    assert reply(admin, item).status_code == 200
    shown = mini.get(MINI + "/" + item["id"]).json()["latest_event_id"]
    barrier = Barrier(3)

    def user_add():
        barrier.wait()
        return supplement(mini, item)

    def admin_add():
        barrier.wait()
        return reply(admin, item, status="resolved")

    def read():
        barrier.wait()
        return mini.put(MINI + "/" + item["id"] + "/read", json={"event_id": shown}, headers=key())

    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = [pool.submit(action) for action in [user_add, admin_add, read]]
        assert [job.result().status_code for job in jobs] == [200, 200, 200]
    final = mini.get(MINI + "/" + item["id"]).json()
    assert [event["id"] for event in final["events"]] == [1, 2, 3, 4]
    assert final["unread"] is True
    assert final["status"] == ("pending" if final["events"][-1]["actor"] == "user" else "resolved")
