"""Possessives and administrator-selected sources across both coordinate systems."""

from copy import deepcopy

import pytest

from juya_api.content_contracts import SceneContent
from juya_api.content_service import normalize
from juya_api.listening_vocabulary import resolve_vocabulary_sources


def resolve(module, sentence, word):
    if module == "scene":
        return normalize(
            SceneContent.model_validate(
                {"dialogue": [{"id": "line-1", "english": sentence}], "vocabulary": [word]}
            )
        )["vocabulary"][0]
    payload = {"body_en": sentence, "vocabulary": [deepcopy(word)]}
    resolve_vocabulary_sources(payload)
    return payload["vocabulary"][0]


@pytest.mark.parametrize("module", ["scene", "listening"])
@pytest.mark.parametrize(
    "english,actual",
    [("vine", "vine's"), ("vine", "vine’s"), ("child", "children’s"), ("John", "John's")],
)
def test_possessive_keeps_complete_actual_form_and_original_offsets(module, english, actual):
    word = resolve(module, "😀 " + actual + " root.", {"english": english})
    source = word["source"]
    assert source
    assert source["quote" if module == "scene" else "word"] == actual
    assert source["start" if module == "scene" else "word_start"] == (3 if module == "scene" else 2)


@pytest.mark.parametrize("module", ["scene", "listening"])
def test_unrelated_possessive_is_not_automatically_approved(module):
    word = resolve(module, "The vineyard’s root.", {"english": "vine"})
    assert word["source"] is None


@pytest.mark.parametrize("module", ["scene", "listening"])
@pytest.mark.parametrize("apostrophe", ["'", "’"])
def test_possessive_does_not_bypass_ambiguous_verb_and_noun_review(module, apostrophe):
    word = resolve(module, f"The saw{apostrophe}s blade is sharp.", {"english": "see"})
    assert word["source"] is None
    assert word["source_reason"] == "source_ambiguous"


def manual_source(module):
    if module == "scene":
        return {
            "line_id": "line-1",
            "start": 12,
            "end": 17,
            "quote": "cacti",
            "manual_english": "cactus",
        }
    return {
        "start": 0,
        "end": 17,
        "quote": "😀 We found cacti.",
        "word_start": 11,
        "word_end": 16,
        "word": "cacti",
        "confirmed": True,
        "manual_english": "cactus",
    }


@pytest.mark.parametrize("module", ["scene", "listening"])
def test_manual_unknown_form_survives_preview_save_and_publish(admin, module):
    from .content_helpers import draft, key, publish
    from .test_integration06 import A, article, category
    from .test_integration06 import publish as publish_listening

    sentence = "😀 We found cacti."
    word = {"id": "w", "english": "cactus", "meaning": "仙人掌", "source_hint": "Old quote."}
    if module == "scene":
        row = draft(admin)
        route = f"/api/admin/v1/cards/{row['id']}"
        payload = {
            **row["content"],
            "dialogue": [
                {"id": "line-1", "speaker": "A", "english": sentence, "chinese": "发现仙人掌"}
            ],
            "vocabulary": [word],
        }
        update = {"revision": row["draft_revision"], "content": payload}
        field, revision = "content", "draft_revision"
    else:
        owner = category(admin)
        row = article(admin, owner["id"])
        route = f"{A}/articles/{row['id']}"
        payload = {**row["payload"], "body_en": sentence, "vocabulary": [word]}
        update = {"revision": row["revision"], "category_id": owner["id"], "payload": payload}
        field, revision = "payload", "revision"
    unresolved = admin.put(route, headers=key(), json=update)
    assert unresolved.status_code == 200, unresolved.text
    rejected = admin.post(
        route + ("/preview" if module == "scene" else "/publish"),
        headers=key(),
        json={"revision": unresolved.json()[revision]},
    )
    assert rejected.status_code == 422, rejected.text
    word["source"] = manual_source(module)
    preview = admin.post(
        "/api/admin/v1/vocabulary/sources/preview", json={"module": module, "content": payload}
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["vocabulary"][0]["source"] == manual_source(module)
    update["revision"] = unresolved.json()[revision]
    saved = admin.put(route, headers=key(), json=update)
    assert saved.status_code == 200, saved.text
    assert saved.json()[field]["vocabulary"][0]["source"] == manual_source(module)
    live = (
        publish(admin, saved.json())
        if module == "scene"
        else publish_listening(admin, saved.json())
    )
    assert live[field]["vocabulary"][0]["source"] == manual_source(module)
    assert not live[field]["vocabulary"][0].get("source_reason")


@pytest.mark.parametrize("module", ["scene", "listening"])
@pytest.mark.parametrize("change", ["word", "body", "quote", "range"])
def test_invalid_manual_evidence_requires_review(module, change):
    word = {"id": "w", "english": "cactus", "meaning": "仙人掌", "source": manual_source(module)}
    sentence = "😀 We found cacti."
    if change == "word":
        word["english"] = "flower"
    elif change == "body":
        sentence = "😀 We found roses."
    elif change == "quote":
        word["source"]["quote"] = "fabricated"
    else:
        word["source"]["end"] = 200
    result = resolve(module, sentence, word)
    assert result["source"] is None
    assert result["source_reason"] == "source_manual_invalid"


@pytest.mark.parametrize("module", ["scene", "listening"])
def test_explicit_manual_senses_can_share_a_real_fragment(module):
    sentence = "😀 We found cacti."
    words = [
        {"id": str(i), "english": "cactus", "meaning": meaning, "source": manual_source(module)}
        for i, meaning in enumerate(["仙人掌", "仙人掌科植物"])
    ]
    if module == "scene":
        words = normalize(
            SceneContent.model_validate(
                {"dialogue": [{"id": "line-1", "english": sentence}], "vocabulary": words}
            )
        )["vocabulary"]
    else:
        resolve_vocabulary_sources({"body_en": sentence, "vocabulary": words})
    assert all(w["source"] == manual_source(module) for w in words)
