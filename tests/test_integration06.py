"""Integration06 category ownership, explicit free access and vocabulary contracts."""

from sqlalchemy import select

from tests.content_helpers import key, recording

A = "/api/admin/v1/listening"
M = "/api/mini/v1/listening"


def category(admin, name="日常"):
    """Create a direct article owner without creating any topic."""
    result = admin.post(A + "/categories", json={"name": name}, headers=key())
    assert result.status_code == 200, result.text
    return result.json()


def article(admin, category_id, vocabulary=None):
    """Create and populate a publishable direct-category article."""
    result = admin.post(
        A + "/articles", json={"category_id": category_id, "payload": {}}, headers=key()
    )
    assert result.status_code == 200, result.text
    row = result.json()
    audio = admin.post(
        A + f"/articles/{row['id']}/media?kind=audio",
        headers=key(),
        files={"file": ("a.wav", recording(), "audio/wav")},
    )
    assert audio.status_code == 200, audio.text
    payload = {
        "title_zh": "休息",
        "title_en": "A break",
        "body_en": "We rest. We rested.",
        "translation_zh": "我们休息。",
        "expressions": [{"english": "take a break", "chinese": "休息", "example": "Take a break."}]
        * 5,
        "audio_id": audio.json()["id"],
        "vocabulary": vocabulary or [],
    }
    update = admin.put(
        A + f"/articles/{row['id']}",
        json={"category_id": category_id, "revision": row["revision"], "payload": payload},
        headers=key(),
    )
    assert update.status_code == 200, update.text
    return update.json()


def publish(admin, row):
    """Publish the checked draft without a legacy topic or free-count setup."""
    result = admin.post(
        A + f"/articles/{row['id']}/publish", json={"revision": row["revision"]}, headers=key()
    )
    assert result.status_code == 200, result.text
    return result.json()


def free(admin, row, enabled=True):
    """Change only the independent free revision."""
    path = A + f"/articles/{row['id']}/free-access"
    old = admin.get(path)
    assert old.status_code == 200, old.text
    response = admin.put(
        path, json={"is_free": enabled, "revision": old.json()["revision"]}, headers=key()
    )
    assert response.status_code == 200, response.text
    return response.json()


def vocabulary():
    """Use exact Unicode codepoint sentence and word references."""
    return [
        {
            "id": "rest-one",
            "english": "rest",
            "meaning": "休息",
            "phonetic": "/rest/",
            "source": {
                "start": 0,
                "end": 8,
                "quote": "We rest.",
                "word_start": 3,
                "word_end": 7,
                "word": "rest",
                "confirmed": True,
            },
        }
    ]


def test_direct_category_publish_free_access_and_revocation(admin, mini, system):
    from juya_api.listening_models import ListeningTopic

    owner = category(admin)
    row = publish(admin, article(admin, owner["id"], vocabulary()))
    assert row["category_id"] == owner["id"]
    with system["sessions"]() as db:
        assert db.scalar(select(ListeningTopic)) is None
    assert mini.get(M + f"/articles/{row['id']}").status_code == 403
    changed = free(admin, row)
    assert changed == {"is_free": True, "revision": 2, "effective": True}
    assert admin.get(A + f"/articles/{row['id']}").json()["revision"] == row["revision"]
    detail = mini.get(M + f"/articles/{row['id']}").json()
    assert detail["access"]["can_learn"] and not detail["access"]["can_lookup"]
    assert detail["payload"]["vocabulary"][0]["english"] == "rest"
    assert (
        mini.get(
            M + f"/articles/{row['id']}/words/rest-one/pronunciation",
            params={"version_id": row["version_id"]},
        ).status_code
        == 200
    )
    free(admin, row, False)
    assert (
        mini.get(
            M + f"/articles/{row['id']}/words/rest-one/pronunciation",
            params={"version_id": row["version_id"]},
        ).status_code
        == 403
    )


def test_category_move_preserves_version_and_category_next(admin, mini):
    first_owner, second_owner = category(admin), category(admin, "其他")
    first = publish(admin, article(admin, first_owner["id"]))
    second = publish(admin, article(admin, first_owner["id"]))
    free(admin, first)
    free(admin, second)
    assert mini.get(M + f"/articles/{first['id']}/next").json()["article"]["id"] == second["id"]
    update = admin.put(
        A + f"/articles/{first['id']}",
        json={
            "revision": first["revision"],
            "category_id": second_owner["id"],
            "payload": first["payload"],
        },
        headers=key(),
    )
    assert update.status_code == 200, update.text
    draft = update.json()
    assert draft["draft_category_id"] == second_owner["id"]
    assert (
        mini.get(M + f"/articles/{first['id']}/summary").json()["category_id"] == first_owner["id"]
    )
    moved = publish(admin, draft)
    assert moved["version_id"] == first["version_id"]
    assert mini.get(M + f"/articles/{first['id']}/next").json()["ended"]
    page = mini.get(M + "/articles", params={"category_id": second_owner["id"]}).json()
    assert [item["id"] for item in page["items"]] == [first["id"]]
    blocked = admin.post(
        A + f"/categories/{second_owner['id']}/delete",
        json={"revision": second_owner["revision"]},
        headers=key(),
    )
    assert blocked.status_code == 409


def test_vocabulary_source_must_match_current_body_and_semantic_hash(admin, system):
    from juya_api.listening_imports import source_hash

    owner = category(admin)
    row = article(admin, owner["id"], vocabulary())
    payload = {**row["payload"], "body_en": "We changed."}
    invalid = admin.put(
        A + f"/articles/{row['id']}",
        json={"revision": row["revision"], "category_id": owner["id"], "payload": payload},
        headers=key(),
    )
    assert invalid.status_code == 200
    invalid_publish = admin.post(
        A + f"/articles/{row['id']}/publish",
        json={"revision": invalid.json()["revision"]},
        headers=key(),
    )
    assert invalid_publish.status_code == 422
    with system["sessions"]() as db:
        original = row["payload"]
        renamed = {
            **original,
            "vocabulary": [{**original["vocabulary"][0], "id": "another-random-id"}],
        }
        assert source_hash(db, original) == source_hash(db, renamed)
        empty = {**original, "vocabulary": []}
        old = {name: value for name, value in empty.items() if name != "vocabulary"}
        assert source_hash(db, empty) == source_hash(db, old)


def test_legacy_configuration_writes_are_gone(admin):
    assert (
        admin.post(
            A + "/topics",
            json={"name": "旧", "name_en": "old", "category_id": category(admin)["id"]},
            headers=key(),
        ).status_code
        == 410
    )
    assert (
        admin.put(
            A + "/free-policy", json={"free_count": 1, "revision": 0}, headers=key()
        ).status_code
        == 410
    )
    assert (
        admin.post(
            "/api/admin/v1/learning-access/free-policy/preview",
            json={"free_count": 1},
            headers=key(),
        ).status_code
        == 410
    )


def test_unconfirmed_words_and_changed_body_can_be_saved_as_drafts(admin):
    """Source review must not prevent saving a body edit or unfinished vocabulary."""
    owner = category(admin)
    row = article(admin, owner["id"], [{**vocabulary()[0], "source": None}])
    result = admin.post(
        A + f"/articles/{row['id']}/publish", json={"revision": row["revision"]}, headers=key()
    )
    assert result.status_code == 422
    assert "vocabulary:" in result.text


def test_independent_free_receipt_stale_revision_offline_and_no_replacement(admin, mini):
    """A replay changes no other object and offline/republication preserves the flag."""
    owner = category(admin)
    row = publish(admin, article(admin, owner["id"]))
    other = publish(admin, article(admin, owner["id"]))
    path = A + f"/articles/{row['id']}/free-access"
    body, headers = {"is_free": True, "revision": 1}, key()
    accepted = admin.put(path, json=body, headers=headers)
    assert accepted.status_code == 200
    assert admin.put(path, json=body, headers=headers).json() == accepted.json()
    assert admin.put(path, json={"is_free": False, "revision": 1}, headers=key()).status_code == 409
    offline = admin.post(
        A + f"/articles/{row['id']}/offline", json={"revision": row["revision"]}, headers=key()
    ).json()
    assert admin.get(path).json() == {"is_free": True, "revision": 2, "effective": False}
    reopened = publish(admin, offline)
    assert reopened["version_id"] == row["version_id"]
    deleted = admin.post(
        A + f"/articles/{row['id']}/delete", json={"revision": reopened["revision"]}, headers=key()
    )
    assert deleted.status_code == 200
    assert admin.put(path, json={"is_free": True, "revision": 2}, headers=key()).status_code == 410
    assert mini.get(M + f"/articles/{other['id']}/summary").json()["access"]["is_free"] is False
    assert admin.get(A + "/free-policy").json()["article_ids"] == []


def test_word_audio_tickets_recheck_free_state_for_get_head_and_range(admin, mini, system):
    """Cached speech never bypasses current publication access after its URL is issued."""
    from juya_api.job_models import Job
    from juya_api.listening_pronunciation import reference
    from juya_api.pronunciation_models import Pronunciation

    owner = category(admin)
    row = publish(admin, article(admin, owner["id"], vocabulary()))
    free(admin, row)
    path = M + f"/articles/{row['id']}/words/rest-one/pronunciation"
    generated = mini.post(path, json={"version_id": row["version_id"]}, headers=key())
    assert generated.status_code == 200, generated.text
    uid = mini.get("/api/mini/v1/me").json()["id"]
    with system["sessions"].begin() as db:
        _, _, _, cache_key = reference(
            db,
            system["settings"],
            "mini",
            uid,
            row["id"],
            "rest-one",
            row["version_id"],
            now=system["time"][0],
        )
        cache = db.get(Pronunciation, cache_key)
        db.get(Job, cache.job_id).state = "succeeded"
        cache.media_id = row["payload"]["audio_id"]
    ready = mini.get(path, params={"version_id": row["version_id"]}).json()
    assert ready["state"] == "ready"
    assert mini.get(ready["url"]).status_code == 200
    free(admin, row, False)
    assert mini.get(ready["url"]).status_code == 403
    assert mini.head(ready["url"]).status_code == 403
    assert mini.get(ready["url"], headers={"Range": "bytes=0-15"}).status_code == 403


def test_deleted_article_allows_category_soft_delete_with_historical_foreign_keys(admin, system):
    """Deleted article references are retained without preventing removal from live catalog."""
    from juya_api.listening_models import ListeningArticle, ListeningCategory

    owner = category(admin)
    row = article(admin, owner["id"])
    assert (
        admin.post(
            A + f"/articles/{row['id']}/delete", json={"revision": row["revision"]}, headers=key()
        ).status_code
        == 200
    )
    removed = admin.post(
        A + f"/categories/{owner['id']}/delete", json={"revision": owner["revision"]}, headers=key()
    )
    assert removed.status_code == 200, removed.text
    assert admin.get(A + "/categories").json()["items"] == []
    with system["sessions"]() as db:
        assert db.get(ListeningCategory, owner["id"]).deleted_at
        assert db.get(ListeningArticle, row["id"]).category_id == owner["id"]


def test_new_scene_is_nonfree_until_explicit_flag_and_draft_revision_is_independent(admin, mini):
    """Publish a scene through real endpoints without the legacy free fixture helper."""
    from tests.content_helpers import draft

    row = draft(admin)
    preview = admin.post(
        f"/api/admin/v1/cards/{row['id']}/preview",
        json={"revision": row["draft_revision"]},
        headers=key(),
    ).json()
    live = admin.post(
        f"/api/admin/v1/cards/{row['id']}/publish",
        json={"revision": row["draft_revision"], "preview_id": preview["preview_id"]},
        headers=key(),
    )
    assert live.status_code == 200
    live = live.json()
    assert live["is_free"] is False and live["free_revision"] == 1
    assert mini.get(f"/api/mini/v1/cards/{row['id']}").status_code == 403
    state = admin.put(
        f"/api/admin/v1/cards/{row['id']}/free-access",
        json={"is_free": True, "revision": 1},
        headers=key(),
    )
    assert state.json() == {"is_free": True, "revision": 2, "effective": True}
    updated = admin.get(f"/api/admin/v1/cards/{row['id']}").json()
    assert updated["draft_revision"] == live["draft_revision"]
    assert updated["current_version_id"] == live["current_version_id"]
    assert updated["is_free"] and updated["free_revision"] == 2


def test_template_word_table_resolves_unique_quote_and_keeps_ambiguous_senses_separate():
    """Old no-word input stays valid; exact current quote identifies each unique source."""
    import io

    from docx import Document

    from juya_api.listening_imports import parse_docx
    from juya_api.listening_template import template_document

    payload, hints = parse_docx(template_document())
    assert "主题" not in hints
    assert payload["vocabulary"][0]["source"]["quote"] == "Take a break and drink water."
    doc = Document(io.BytesIO(template_document()))
    for paragraph in doc.paragraphs:
        if paragraph.text.startswith("Take a break and drink"):
            paragraph.text = "Take a break. Take a break."
    table = doc.tables[0]
    table.rows[1].cells[3].text = "Take a break."
    for cell, value in zip(
        table.add_row().cells, ["break", "暂停", "", "Take a break."], strict=True
    ):
        cell.text = value
    stream = io.BytesIO()
    doc.save(stream)
    ambiguous, _ = parse_docx(stream.getvalue())
    words = ambiguous["vocabulary"]
    assert len(words) == 2 and words[0]["id"] != words[1]["id"]
    assert all(word["source"] is None for word in words)


def test_unconfirmed_docx_source_hint_is_retained_and_distinguishes_staging_identity():
    """Two unresolved original quotes must not collapse into a duplicate before review."""
    import io

    from docx import Document

    from juya_api.listening_imports import parse_docx
    from juya_api.listening_template import template_document
    from juya_api.listening_vocabulary import canonical_payload

    doc = Document(io.BytesIO(template_document()))
    doc.tables[0].rows[1].cells[3].text = "A different original quote."
    stream = io.BytesIO()
    doc.save(stream)
    payload, _ = parse_docx(stream.getvalue())
    word = payload["vocabulary"][0]
    assert word["source"] is None
    assert word["source_hint"] == "A different original quote."
    changed = {**payload, "vocabulary": [{**word, "source_hint": "Another original quote."}]}
    assert canonical_payload(payload) != canonical_payload(changed)


def test_legacy_missing_empty_vocabulary_reuses_version_without_rewriting_history(admin, system):
    """Adding only the new empty default must preserve immutable old publication payloads."""
    from juya_api.listening_models import ListeningVersion

    owner = category(admin)
    row = publish(admin, article(admin, owner["id"]))
    with system["sessions"].begin() as db:
        version = db.get(ListeningVersion, row["version_id"])
        old = dict(version.payload)
        old.pop("vocabulary")
        version.payload = old
    preview = admin.get(A + f"/articles/{row['id']}").json()
    assert preview["has_unpublished_changes"] is False
    same = publish(admin, preview)
    assert same["version_id"] == row["version_id"]
    assert same["revision"] == row["revision"]
    with system["sessions"]() as db:
        assert "vocabulary" not in db.get(ListeningVersion, row["version_id"]).payload


def test_listening_speech_references_cannot_omit_or_mix_version_fences(admin, mini):
    """Every controlled preview or learner speech request binds exactly one saved revision."""
    owner = category(admin)
    row = publish(admin, article(admin, owner["id"], vocabulary()))
    free(admin, row)
    path = A + f"/articles/{row['id']}/words/rest-one/pronunciation"
    mixed = {"version_id": row["version_id"], "revision": row["revision"]}
    assert admin.post(path, json=mixed, headers=key()).status_code == 422
    assert admin.post(path, json={}, headers=key()).status_code == 422
    batch = admin.post(A + "/imports", json={"mode": "zip"}, headers=key()).json()
    staged = A + f"/imports/{batch['id']}/candidates/unknown/words/rest-one/pronunciation"
    assert admin.post(staged, json={}, headers=key()).status_code == 422
