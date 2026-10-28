"""Regression boundaries found in the revision17 independent review."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from juya_api.access_models import AccessHistory
from juya_api.listening_models import ListeningImport
from tests.content_helpers import key, picture
from tests.test_learning import complete as complete_scene
from tests.test_learning import scene
from tests.test_listening import A, M, article, policy, post, publish, topic
from tests.test_listening_imports import assign, package, upload


def test_thumbnail_ticket_is_session_bound_and_safe_for_restricted_article(admin, mini, system):
    row = article(admin)
    image = admin.post(
        A + f"/articles/{row['id']}/media?kind=image",
        headers=key(),
        files={"file": ("pic.png", picture(), "image/png")},
    ).json()
    row = admin.put(
        A + f"/articles/{row['id']}",
        headers=key(),
        json={
            "revision": row["revision"],
            "topic_id": row["topic_id"],
            "payload": {**row["payload"], "image_id": image["id"]},
        },
    ).json()
    row = publish(admin, row)
    policy(admin, 0)
    grant = mini.get(
        M + f"/articles/{row['id']}/thumbnail-ticket", params={"version_id": row["version_id"]}
    )
    assert grant.status_code == 200, grant.text
    # Image elements send no Bearer; the session-bound short ticket must suffice
    bearer = mini.headers.pop("Authorization")
    try:
        resource = mini.get(grant.json()["url"])
        assert resource.status_code == 200 and resource.headers["content-type"].startswith("image/")
    finally:
        mini.headers["Authorization"] = bearer
    assert (
        mini.get(
            M + f"/articles/{row['id']}/media/{image['id']}",
            params={"version_id": row["version_id"]},
        ).status_code
        == 403
    )
    system["time"][0] += timedelta(minutes=6)
    assert mini.get(grant.json()["url"]).status_code == 401


def test_partial_import_remains_discoverable_after_saving_only_one_candidate(admin):
    t = topic(admin)
    batch = upload(admin, post(admin, A + "/imports", {"mode": "zip"}), package("A"), package("B"))
    for candidate in batch["candidates"]:
        batch = assign(admin, batch, candidate["id"], t["id"])
    first, second = batch["candidates"]
    preview = post(
        admin,
        A + f"/imports/{batch['id']}/preview",
        {"revision": batch["revision"], "candidate_ids": [first["id"]]},
    )
    result = post(
        admin, A + f"/imports/{batch['id']}/save", {"preview_token": preview["preview_token"]}
    )
    assert result["batch"]["status"] == "partial"
    restored = admin.get(A + "/imports?unfinished=true").json()
    assert batch["id"] in [b["id"] for b in restored["items"]]
    remaining = admin.get(A + f"/imports/{batch['id']}").json()
    assert next(c for c in remaining["candidates"] if c["id"] == second["id"])["article_id"] is None


def test_unfinished_import_filter_precedes_pagination_and_ignores_stale_saved_status(admin, system):
    batch = upload(admin, post(admin, A + "/imports", {"mode": "zip"}), package())
    with system["sessions"].begin() as db:
        old = db.get(ListeningImport, batch["id"])
        old.status = "saved"  # restore batches written by the earlier partial-save bug
        for number in range(55):
            db.add(
                ListeningImport(
                    admin_id=old.admin_id,
                    mode="zip",
                    status="saved",
                    packages=[],
                    created_at=old.created_at + timedelta(seconds=number + 1),
                )
            )
        for number in range(51):
            db.add(
                ListeningImport(
                    admin_id=old.admin_id,
                    mode="zip",
                    packages=[],
                    created_at=old.created_at + timedelta(seconds=number + 60),
                )
            )
    first = admin.get(A + "/imports?unfinished=true&limit=50&page=1").json()
    second = admin.get(A + "/imports?unfinished=true&limit=50&page=2").json()
    assert first["total"] == 52
    assert batch["id"] in [b["id"] for b in second["items"]]
    assert len(first["items"]) == 50 and len(second["items"]) == 2


def test_recent_study_uses_successful_scene_and_listening_completions_including_review(
    admin, mini, system
):
    assert mini.get(M + "/statistics").json()["last_studied_at"] is None
    row = publish(admin, article(admin))
    policy(admin, 1)
    path = M + f"/articles/{row['id']}/complete"
    result = post(mini, path, {"version_id": row["version_id"]})
    assert result["statistics"]["last_studied_at"] == "2026-10-17T08:00:00.000000Z"
    card, version = scene(admin)
    system["time"][0] = datetime(2026, 10, 17, 9, tzinfo=UTC)
    assert (
        complete_scene(mini, card, version).json()["statistics"]["last_studied_at"]
        == "2026-10-17T09:00:00.000000Z"
    )
    system["time"][0] = datetime(2026, 10, 18, 8, tzinfo=UTC)
    result = post(mini, path, {"version_id": row["version_id"]})
    assert result["statistics"]["last_studied_at"] == "2026-10-18T08:00:00.000000Z"
    owner = mini.get("/api/mini/v1/me").json()["id"]
    assert admin.get(f"/api/admin/v1/users/{owner}").json()["statistics"] == result["statistics"]


def test_m_and_both_order_scopes_persist_before_after_audit_once(admin, system):
    t = topic(admin)
    rows = [publish(admin, article(admin, t["id"], str(i))) for i in range(2)]
    policy(admin, 1)
    for scope in ["topic", "global"]:
        order = admin.get(A + "/order", params={"scope": scope, "topic_id": t["id"]}).json()
        body = {
            **order,
            "scope": scope,
            "topic_id": t["id"] if scope == "topic" else None,
            "article_ids": [r["id"] for r in reversed(rows)],
        }
        headers = key()
        first = admin.put(A + "/order", json=body, headers=headers)
        assert first.status_code == 200, first.text
        assert admin.put(A + "/order", json=body, headers=headers).json() == first.json()
    with system["sessions"]() as db:
        history = list(
            db.scalars(
                select(AccessHistory)
                .where(AccessHistory.action.like("listening.%"))
                .order_by(AccessHistory.occurred_at)
            )
        )
        assert len(history) == 3
        free = next(h for h in history if h.action == "listening.free-policy")
        assert free.before["configured"] is False and free.after["free_count"] == 1
        assert free.after["article_ids"] == [rows[0]["id"]]
        orders = [h for h in history if h.action == "listening.order"]
        assert {h.after["scope"] for h in orders} == {"global", "topic"}
        assert all(h.before["article_ids"] == [r["id"] for r in rows] for h in orders)
        assert all(h.after["article_ids"] == [r["id"] for r in reversed(rows)] for h in orders)
        global_order = next(h for h in orders if h.after["scope"] == "global")
        assert global_order.before["policy"]["article_ids"] == [rows[0]["id"]]
        assert global_order.after["policy"]["article_ids"] == [rows[1]["id"]]
