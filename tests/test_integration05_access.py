"""R06 explicit local account states with direct M updates, never inferred from UI."""

from datetime import UTC, datetime

from sqlalchemy import update

from tests.content_helpers import key
from tests.test_learning_access import change, user_id
from tests.test_listening import A, M, article, post, topic


def test_direct_m_ten_to_one_zero_and_all_authorization_states(admin, mini, system):
    from juya_api.models import AdminSession, MiniSession

    with system["sessions"].begin() as db:
        for model in [AdminSession, MiniSession]:
            db.execute(update(model).values(expires_at=datetime(2030, 1, 1)))
    t = topic(admin)
    rows = [
        post(admin, A + f"/articles/{row['id']}/publish", {"revision": row["revision"]})
        for row in [article(admin, t["id"], str(n)) for n in range(10)]
    ]

    def count(n):
        current = admin.get(A + "/free-policy").json()
        response = admin.put(
            A + "/free-policy",
            headers=key(),
            json={"free_count": n, "revision": current["revision"]},
        )
        assert response.status_code == 200, response.text

    count(10)
    target = rows[-1]
    detail = mini.get(M + f"/articles/{target['id']}").json()
    ticket = post(
        mini,
        M + f"/articles/{target['id']}/media-ticket",
        {"version_id": detail["version_id"], "media_id": target["payload"]["audio_id"]},
    )
    post(mini, M + f"/articles/{target['id']}/complete", {"version_id": detail["version_id"]})
    assert (
        mini.put(
            M + f"/articles/{target['id']}/favorite",
            json={"version_id": detail["version_id"]},
            headers=key(),
        ).status_code
        == 200
    )
    count(1)
    for row in rows:
        assert mini.get(M + f"/articles/{row['id']}").status_code == (
            200 if row["id"] == rows[0]["id"] else 403
        )
    assert mini.get(M + "/favorites").json()["items"][0]["access"]["can_learn"] is False
    assert mini.get(M + "/records").json()["items"][0]["access"]["can_learn"] is False
    for headers in [{}, {"Range": "bytes=0-15"}]:
        assert mini.get(ticket["url"], headers=headers).status_code == 403
    assert mini.head(ticket["url"]).status_code == 403
    uid = user_id(mini)
    change(admin, uid, "grant")
    assert mini.get(M + f"/articles/{target['id']}").status_code == 200
    count(0)
    assert mini.get(M + f"/articles/{target['id']}").status_code == 200
    change(admin, uid, "revoke")
    assert mini.get(M + f"/articles/{rows[0]['id']}").status_code == 403
    assert mini.get("/api/mini/v1/learning-access").json()["free_count"] is None
    change(admin, uid, "grant")
    system["time"][0] = datetime(2026, 12, 20, tzinfo=UTC)
    assert mini.get(M + f"/articles/{target['id']}").status_code == 403
    assert mini.get(M + "/statistics").json()["completed_articles"] == 1
