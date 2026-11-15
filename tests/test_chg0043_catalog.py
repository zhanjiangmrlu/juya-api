from .content_helpers import content, draft, key, publish

TYPES = "/api/admin/v1/content-types"
CARDS = "/api/admin/v1/cards"


def historical_card(admin, system):
    """Seed the exact state of an existing publication immediately after migration 0029."""
    from sqlalchemy import delete

    from juya_api.content_models import Card, CardContentTypeVersion, CardDraft

    row = publish(admin, draft(admin))
    with system["sessions"].begin() as db:
        card = db.get(Card, row["id"])
        card.current_content_type_version_id = None
        card.published_content_type = None
        db.get(CardDraft, card.id).content_type = None
        db.execute(delete(CardContentTypeVersion).where(CardContentTypeVersion.card_id == card.id))
    return row


def test_explicit_type_requires_pdf_even_before_enable(admin):
    row = admin.post(
        CARDS, json={"content": content(admin), "content_type": "intensive"}, headers=key()
    ).json()
    response = admin.post(f"{CARDS}/{row['id']}/preview", json={"revision": 1}, headers=key())
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["code"] == "intensive_pdf_required"


def test_history_confirm_enable_and_draft_isolation(admin, mini, system):
    row = historical_card(admin, system)
    assert admin.post(TYPES + "/enable", json={}, headers=key()).status_code == 409
    snapshot = admin.get(TYPES + "/history").json()["items"][0]
    assert snapshot["suggestion"] == "illustrated"
    selection = {
        "items": [
            {"card_id": row["id"], "snapshot": snapshot["snapshot"], "content_type": "illustrated"}
        ]
    }
    repeat_key = key()
    first = admin.post(TYPES + "/confirm", json=selection, headers=repeat_key).json()
    assert first["items"][0]["status"] == "confirmed"
    assert admin.post(TYPES + "/confirm", json=selection, headers=repeat_key).json() == first
    assert (
        admin.post(TYPES + "/confirm", json=selection, headers=key()).json()["items"][0]["status"]
        == "skipped"
    )
    assert admin.post(TYPES + "/enable", json={}, headers=key()).json()["content_types_ready"]
    now = admin.get(CARDS + "/" + row["id"]).json()
    assert now["current_version_id"] == row["current_version_id"]
    edited = admin.put(
        CARDS + "/" + row["id"],
        json={
            "content_type": "intensive",
            "revision": now["draft_revision"],
            "content": now["content"],
        },
        headers=key(),
    ).json()
    assert (
        edited["published_content_type"] == "illustrated"
        and edited["draft_content_type"] == "intensive"
    )
    stats = admin.get(CARDS + "?content_type=illustrated&search=missing&page=40").json()
    assert stats["statistics"] == {"total": 1, "published": 1, "free": 1, "remaining": 0}
    assert stats["total"] == stats["total_pages"] == 0 and stats["page"] == 1
    endpoint = "/api/mini/v1/cards?content_type=illustrated"
    assert mini.get(endpoint).json()["type_published_total"] == 1
    queue = mini.post(
        "/api/mini/v1/learning-queues",
        json={"source": "learning", "content_type": "illustrated", "card_id": row["id"]},
        headers=key(),
    )
    assert queue.status_code == 201
    completed = mini.post(
        f"/api/mini/v1/cards/{row['id']}/complete",
        json={"version_id": row["current_version_id"]},
        headers=key(),
    )
    assert completed.status_code == 200
    assert mini.get(endpoint).json()["total"] == 0
    assert (
        mini.get("/api/mini/v1/learning-queues/" + queue.json()["id"]).json()["items"][0][
            "available"
        ]
        is False
    )
    mini.headers.pop("Authorization")
    assert mini.get(endpoint).json()["total"] == 1
    assert mini.get("/api/mini/v1/cards?content_type=intensive").json()["total"] == 0


def test_unready_typed_request_and_listening_aggregation(admin, system):
    page = system["mini"].get("/api/mini/v1/cards?content_type=intensive").json()
    assert page.get("content_types_ready") is False and page["type_published_total"] is None
    data = admin.get("/api/admin/v1/listening/articles?page=40").json()
    assert data.get("statistics") == {"total": 0, "published": 0, "free": 0, "remaining": 0}
    assert data["total_pages"] == 0 and data["page"] == 1


def test_explicit_null_pdf_changes_and_binding_corruption(admin, system):
    from juya_api.content_models import Card

    from .test_study_notes import process_jobs, upload

    body = content(admin)
    medium = upload(admin)
    process_jobs(admin)
    note = {"action": "set", "media_id": medium["id"]}

    def add(value, note=None):
        return admin.post(
            CARDS, json={"content": body, "content_type": value, "study_note": note}, headers=key()
        ).json()

    def errors(row):
        response = admin.post(
            CARDS + "/" + row["id"] + "/preview",
            json={"revision": row["draft_revision"]},
            headers=key(),
        )
        assert response.status_code == 422
        return {e["code"] for e in response.json()["error"]["details"]}

    assert "content_type_required" in errors(add(None))
    assert "illustrated_pdf_conflict" in errors(add("illustrated", note))
    live = publish(admin, add("intensive", note))
    old_version = live["current_version_id"]
    assert admin.post(TYPES + "/enable", json={}, headers=key()).status_code == 200
    changed = admin.put(
        CARDS + "/" + live["id"],
        json={
            "content_type": "illustrated",
            "study_note": {"action": "remove"},
            "content": body,
            "revision": live["draft_revision"],
        },
        headers=key(),
    ).json()
    assert system["mini"].get("/api/mini/v1/cards?content_type=intensive").json()["total"] == 1
    new = publish(admin, changed)
    assert new["current_version_id"] == old_version and new["sort_order"] == live["sort_order"]
    assert new["published_study_note"] is None and new["published_content_type"] == "illustrated"
    assert "content_type_required" in errors(draft(admin, body, content_type=None))
    with system["sessions"].begin() as db:
        db.get(Card, live["id"]).current_content_type_version_id = None
    broken = system["mini"].get("/api/mini/v1/cards?content_type=illustrated")
    assert (
        broken.status_code == 503
        and broken.json()["error"]["code"] == "content_type_bindings_invalid"
    )


def test_classified_queue_excludes_restricted_and_other_types(admin, mini):
    payload = content(admin)
    live = []
    for i in range(3):
        d = admin.post(
            CARDS,
            json={"content": dict(payload, name=str(i)), "content_type": "illustrated"},
            headers=key(),
        ).json()
        live.append(publish(admin, d))
    row = live[0]
    free = admin.get(CARDS + "/" + row["id"] + "/free-access").json()
    assert (
        admin.put(
            CARDS + "/" + row["id"] + "/free-access",
            json={"is_free": False, "revision": free["revision"]},
            headers=key(),
        ).status_code
        == 200
    )
    assert admin.post(TYPES + "/enable", json={}, headers=key()).status_code == 200
    listing = mini.get("/api/mini/v1/cards?content_type=illustrated").json()
    assert listing["total"] == 3 and not listing["items"][-1]["access"]["can_learn"]
    first = listing["items"][0]["id"]
    queue = mini.post(
        "/api/mini/v1/learning-queues", json={"source": "learning", "card_id": first}, headers=key()
    ).json()
    assert queue.get("content_type") == "illustrated" and queue["total"] == 2
    assert (
        mini.post(
            "/api/mini/v1/learning-queues",
            json={"source": "learning", "content_type": "intensive", "card_id": first},
            headers=key(),
        ).status_code
        == 409
    )


def test_mysql_history_confirmation_rechecks_after_catalog_writer(admin, system):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError
    from threading import Event

    import pytest
    from sqlalchemy import func, select

    from juya_api.content_models import CardContentTypeVersion, CardDraft
    from juya_api.content_service import catalog_lock

    if system["engine"].dialect.name != "mysql":
        pytest.skip("Requires real MySQL catalog row locking")
    row = historical_card(admin, system)
    view = admin.get(TYPES + "/history").json()["items"][0]
    started = Event()

    def confirm():
        started.set()
        return admin.post(
            TYPES + "/confirm",
            headers=key(),
            json={
                "items": [
                    {
                        "card_id": row["id"],
                        "snapshot": view["snapshot"],
                        "content_type": "illustrated",
                    }
                ]
            },
        )

    with ThreadPoolExecutor(max_workers=1) as pool:
        with system["sessions"].begin() as db:
            catalog_lock(db)
            future = pool.submit(confirm)
            assert started.wait(timeout=3)
            with pytest.raises(TimeoutError):
                future.result(timeout=0.3)
            d = db.get(CardDraft, row["id"])
            d.revision += 1
            d.content_type = "intensive"
        receipt = future.result(timeout=10).json()["items"][0]
        assert receipt["reason"] == "snapshot_changed"
    with system["sessions"]() as db:
        assert db.scalar(select(func.count()).select_from(CardContentTypeVersion)) == 0
    new = admin.get(TYPES + "/history").json()["items"][0]
    result = admin.post(
        TYPES + "/confirm",
        headers=key(),
        json={
            "items": [
                {"card_id": row["id"], "snapshot": new["snapshot"], "content_type": "illustrated"}
            ]
        },
    )
    assert result.json()["items"][0]["status"] == "confirmed"
    view = admin.get(CARDS + "/" + row["id"]).json()
    assert (
        view["published_content_type"] == "illustrated"
        and view["draft_content_type"] == "intensive"
    )


def test_legacy_request_without_type_cannot_publish_before_catalog_activation(admin):
    row = admin.post(CARDS, json={"content": content(admin)}, headers=key()).json()
    response = admin.post(
        CARDS + "/" + row["id"] + "/preview",
        json={"revision": row["draft_revision"]},
        headers=key(),
    )
    assert response.status_code == 422
    assert "content_type_required" in {e["code"] for e in response.json()["error"]["details"]}


def test_two_admin_catalogs_count_100_80_30_independently_of_search(admin, system):
    from juya_api.content_models import Card, CardDraft, CardVersion
    from juya_api.listening_models import ListeningArticle, ListeningVersion

    from .test_integration06 import category

    owner, pending = category(admin), category(admin, "待发布分类")
    now = system["time"][0]
    payload = content(admin)
    with system["sessions"].begin() as db:
        for i in range(100):
            id_ = f"stat-{i}"
            live = i < 80
            status = "published" if live else "offline" if i < 90 else "draft"
            version = f"v-{i}" if i < 90 else None
            free = i < 30 or not live
            db.add(
                Card(
                    id=id_,
                    status=status,
                    is_free=free,
                    current_version_id=version,
                    published_content_type="illustrated" if version else None,
                )
            )
            db.add(
                ListeningArticle(
                    id=id_,
                    category_id=owner["id"],
                    draft_category_id=pending["id"] if version else None,
                    payload={"title_zh": "统计", "title_en": "Count"},
                    status=status,
                    version_id=version,
                    is_free=free,
                )
            )
            db.flush()
            db.add(
                CardDraft(
                    card_id=id_,
                    payload=payload,
                    content_type="intensive" if version else "illustrated",
                )
            )
            if version:
                db.add(
                    CardVersion(
                        id=version,
                        card_id=id_,
                        number=1,
                        payload=payload,
                        content_hash="a" * 64,
                        published_at=now,
                    )
                )
                db.add(
                    ListeningVersion(
                        id=version,
                        article_id=id_,
                        payload={"title_zh": "统计", "title_en": "Count"},
                        published_at=now,
                    )
                )
    summary = {"total": 100, "published": 80, "free": 30, "remaining": 50}
    for path in [
        CARDS + "?content_type=illustrated&search=no-such-text",
        "/api/admin/v1/listening/articles?category_id=" + owner["id"] + "&q=no-such-text",
    ]:
        result = admin.get(path + "&page=99&status=offline").json()
        assert result["statistics"] == result["all_statistics"] == summary
        assert result["total"] == result["total_pages"] == 0 and result["page"] == 1


def test_broken_published_pdf_requires_explicit_removal_to_restore_classification(admin, system):
    from juya_api.content_models import Card

    live = publish(admin, draft(admin))
    with system["sessions"].begin() as db:
        db.get(Card, live["id"]).current_study_note_version_id = "missing-note-version"
    card = admin.get(f"{CARDS}/{live['id']}").json()
    assert "study_note_not_ready" in {issue["code"] for issue in card["issues"]}
    failed = admin.post(
        f"{CARDS}/{live['id']}/preview", json={"revision": card["draft_revision"]}, headers=key()
    )
    assert failed.status_code == 422
    changed = admin.put(
        f"{CARDS}/{live['id']}",
        json={
            "revision": card["draft_revision"],
            "content": card["content"],
            "study_note": {"action": "remove"},
        },
        headers=key(),
    ).json()
    assert publish(admin, changed)["current_version_id"] == live["current_version_id"]
    assert admin.post(TYPES + "/enable", json={}, headers=key()).status_code == 200
