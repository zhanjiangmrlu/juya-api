"""CHG-0015 titles remain versioned, independently editable and importable."""

import io

from docx import Document
from sqlalchemy import select

from juya_api.content_models import CardVersion
from juya_api.import_parser import parse_docx_items

from .content_helpers import content, draft, key, publish
from .test_imports import document


def titled_document(*metadata):
    doc = Document(io.BytesIO(document("戏剧社", "旧模板", titles=False)))
    heading = doc.paragraphs[1]
    for text in metadata:
        heading.insert_paragraph_before(text)
    output = io.BytesIO()
    doc.save(output)
    return output.getvalue()


def test_docx_scopes_english_metadata_to_each_card_and_preserves_case_and_punctuation():
    items = parse_docx_items(titled_document("英文标题:  Choosing a Play: Drama Club!  "))
    assert items[0]["readable"] is True
    assert items[0]["content"]["title_en"] == "Choosing a Play: Drama Club!"
    assert items[1]["content"]["title_en"] == ""
    assert items[0]["content"]["dialogue"][0]["english"] == "Could I get a latte, please?"


def test_conflicting_title_metadata_keeps_readable_dialogue_for_manual_review():
    items = parse_docx_items(titled_document("英文标题：First", "英文标题：Second"))
    assert items[0]["readable"] is True
    assert items[0]["content"]["title_en"] == ""
    assert items[0]["content"]["vocabulary"][0]["english"] == "latte"
    assert any(i["code"] == "title_en_conflict" for i in items[0]["issues"])


def test_new_publication_requires_english_but_incomplete_draft_is_saved(admin):
    payload = content(admin)
    payload.pop("title_en")
    card = draft(admin, payload)
    assert any(i["field"] == "title_en" for i in card["issues"])
    preview = admin.post(
        f"/api/admin/v1/cards/{card['id']}/preview", headers=key(), json={"revision": 1}
    )
    assert preview.status_code == 422


def test_titles_and_optional_meaning_publish_atomically_into_all_learning_summaries(admin, mini):
    payload = dict(content(admin), title_en="Ordering Coffee!")
    payload["vocabulary"][0]["meaning"] = ""
    payload["vocabulary"][0]["phonetic"] = ""
    card = draft(admin, payload)
    assert card["content"]["title_en"] == "Ordering Coffee!"
    assert card["issues"] == []
    first = publish(admin, card)
    card_id = card["id"]
    assert mini.get("/api/mini/v1/cards").json()["items"][0]["title_en"] == "Ordering Coffee!"
    assert admin.get("/api/admin/v1/cards?search=ORDERING").json()["total"] == 1
    assert (
        mini.post(
            f"/api/mini/v1/cards/{card_id}/complete",
            headers=key(),
            json={"version_id": first["current_version_id"]},
        ).status_code
        == 200
    )
    assert (
        mini.put(
            f"/api/mini/v1/cards/{card_id}/favorite",
            headers=key(),
            json={"version_id": first["current_version_id"]},
        ).status_code
        == 200
    )
    saved = admin.put(
        f"/api/admin/v1/cards/{card_id}",
        headers=key(),
        json={"revision": 1, "content": dict(card["content"], title_en="Coffee with Friends")},
    ).json()
    assert (
        mini.get(f"/api/mini/v1/cards/{card_id}").json()["content"]["title_en"]
        == "Ordering Coffee!"
    )
    updated = publish(admin, saved)
    assert updated["id"] == card_id
    for url in [
        "/api/mini/v1/favorites",
        "/api/mini/v1/me/learning-records",
        "/api/mini/v1/me/checkins/2026-10-17",
    ]:
        assert mini.get(url).json()["items"][0]["title_en"] == "Coffee with Friends"


def test_admin_can_search_the_visible_published_title_while_a_candidate_is_renamed(admin):
    card = draft(admin, dict(content(admin), title_en="Original Scene"))
    publish(admin, card)
    admin.put(
        f"/api/admin/v1/cards/{card['id']}",
        headers=key(),
        json={"revision": 1, "content": dict(card["content"], title_en="New Candidate")},
    )
    assert admin.get("/api/admin/v1/cards?search=ORIGINAL").json()["total"] == 1
    assert admin.get("/api/admin/v1/cards?search=candidate").json()["total"] == 1


def test_legacy_published_payload_gets_empty_english_without_rewriting_immutable_version(
    system, admin, mini
):
    card = draft(admin, dict(content(admin), title_en="Ordering Coffee"))
    version_id = publish(admin, card)["current_version_id"]
    with system["sessions"].begin() as db:
        version = db.scalar(select(CardVersion).where(CardVersion.id == version_id))
        legacy = dict(version.payload)
        legacy.pop("title_en", None)
        version.payload = legacy
        old_hash = version.content_hash
    detail = mini.get(f"/api/mini/v1/cards/{card['id']}")
    assert detail.status_code == 200
    assert detail.json()["content"]["title_en"] == ""
    assert mini.get("/api/mini/v1/cards").json()["items"][0]["title_en"] == ""
    with system["sessions"]() as db:
        version = db.get(CardVersion, version_id)
        assert "title_en" not in version.payload
        assert version.content_hash == old_hash


def test_empty_english_does_not_change_historical_import_content_identity():
    from juya_api.import_service import content_hash
    from juya_api.security import fingerprint

    legacy = {
        "name": "旧标题",
        "image_id": None,
        "audio_id": None,
        "dialogue": [],
        "vocabulary": [],
        "chunks": [],
    }
    assert content_hash(None, dict(legacy, title_en="")) == fingerprint(legacy)
