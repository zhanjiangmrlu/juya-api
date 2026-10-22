"""A detail response never mixes a captured header with later accepted events."""

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from .content_helpers import key, picture
from .test_feedback import ADMIN, MINI, SafeContent, create, reply, supplement


@pytest.fixture
def snapshot_feedback(mini, admin):
    mini.app.state.feedback_safety = SafeContent()
    admin.app.state.feedback_safety = SafeContent()
    return mini, admin


def check_snapshot_with_late_append(clients, system, role):
    from juya_api.feedback_models import Feedback
    from juya_api.feedback_service import feedback_view
    from juya_api.models import Administrator, User

    mini, admin = clients
    item = create(mini)
    client, prefix = (mini, MINI) if role == "mini" else (admin, ADMIN)
    if role == "admin":
        assert (
            admin.put(
                ADMIN + "/" + item["id"] + "/read", json={"event_id": 1}, headers=key()
            ).status_code
            == 200
        )
    uploaded = mini.post(
        MINI + "/images", files={"file": ("s.png", picture(), "image/png")}, headers=key()
    )
    assert uploaded.status_code == 201, uploaded.text
    image_id = uploaded.json()["id"]

    # SQLite's production local adapter reserves writers at BEGIN. A plain reader
    # deliberately permits an inter-query commit here, reproducing READ COMMITTED
    # visibility without claiming SQLite verifies MySQL locking or isolation.
    options = (
        {"isolation_level": "READ COMMITTED"} if system["engine"].dialect.name == "mysql" else {}
    )
    engine = create_engine(system["engine"].url, **options)
    appended = False

    @event.listens_for(engine, "before_cursor_execute")
    def append_before_images(connection, cursor, statement, parameters, context, executemany):
        nonlocal appended
        if appended or "FROM feedback_images" not in statement:
            return
        appended = True
        response = (
            reply(admin, item, status="resolved")
            if role == "mini"
            else supplement(mini, item, images=[image_id])
        )
        assert response.status_code == 200, response.text

    try:
        with Session(engine) as reader:
            row = reader.get(Feedback, item["id"])
            actor = (
                reader.get(User, item["user_id"])
                if role == "mini"
                else reader.scalar(select(Administrator))
            )
            request = SimpleNamespace(
                app=client.app, headers=client.headers, cookies=client.cookies
            )
            shown = feedback_view(reader, row, request, actor, role, detail=True)
    finally:
        engine.dispose()

    assert shown["latest_event_id"] == 1
    assert shown["status"] == "pending"
    assert shown["unread"] is False
    assert [entry["id"] for entry in shown["events"]] == [1]
    assert shown["events"][0]["images"] == []
    fresh = client.get(prefix + "/" + item["id"]).json()
    assert fresh["latest_event_id"] == 2
    assert [entry["id"] for entry in fresh["events"]] == [1, 2]
    assert [image["id"] for image in fresh["events"][1]["images"]] == (
        [] if role == "mini" else [image_id]
    )
    assert (
        client.put(
            prefix + "/" + item["id"] + "/read",
            json={"event_id": shown["latest_event_id"]},
            headers=key(),
        ).status_code
        == 200
    )
    assert client.get(prefix + "/unread").json() == {"unread": True, "count": 1}


@pytest.mark.parametrize("role", ["mini", "admin"])
def test_detail_limits_events_and_attachments_to_captured_watermark(
    snapshot_feedback, system, role
):
    check_snapshot_with_late_append(snapshot_feedback, system, role)


@pytest.mark.mysql
@pytest.mark.parametrize("role", ["mini", "admin"])
def test_real_mysql_detail_interquery_append_keeps_snapshot_and_later_unread(
    snapshot_feedback, system, role
):
    if system["engine"].dialect.name != "mysql":
        pytest.skip("Real MySQL READ COMMITTED detail snapshot and inter-query commit")
    check_snapshot_with_late_append(snapshot_feedback, system, role)
