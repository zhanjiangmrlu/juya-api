from juya_api.content_contracts import SceneContent
from juya_api.content_service import normalize
from juya_api.listening_vocabulary import resolve_vocabulary_sources


def test_rules_match_first_reliable_source_using_original_ranges():
    line = "😀 The children ran faster. They ran again."
    scene = normalize(
        SceneContent.model_validate(
            {
                "dialogue": [{"id": "a", "english": line}],
                "vocabulary": [
                    {"english": "run"},
                    {"english": "child"},
                    {"english": "fast"},
                    {"english": "art"},
                ],
            }
        )
    )
    words = scene["vocabulary"]
    assert [w["source"]["quote"] if w["source"] else None for w in words] == [
        "ran",
        "children",
        "faster",
        None,
    ]
    assert words[0]["source"]["start"] == 16
    article = {"body_en": line, "vocabulary": [{"id": "w", "english": "run", "meaning": "跑"}]}
    resolve_vocabulary_sources(article)
    assert article["vocabulary"][0]["source"]["word_start"] == 15
    article["body_en"] = "We run."
    resolve_vocabulary_sources(article)
    assert article["vocabulary"][0]["source"]["word"] == "run"


def test_explicit_hint_and_competing_senses_require_review():
    scene = normalize(
        SceneContent.model_validate(
            {
                "dialogue": [{"id": "a", "english": "We saw a bank."}],
                "vocabulary": [
                    {"english": "bank", "meaning": "银行"},
                    {"english": "bank", "meaning": "河岸"},
                    {"english": "see", "source_hint": "We see the sun."},
                ],
            }
        )
    )
    assert all(w["source"] is None for w in scene["vocabulary"])


def test_edit_preview_uses_saved_matching_rules(admin):
    request = {
        "module": "scene",
        "content": {
            "dialogue": [{"id": "a", "english": "They flew."}],
            "vocabulary": [{"id": "w", "english": "fly", "meaning": "飞"}],
        },
    }
    result = admin.post("/api/admin/v1/vocabulary/sources/preview", json=request)
    assert result.status_code == 200, result.text
    assert result.json()["vocabulary"][0]["source"]["quote"] == "flew"


def test_hearing_typographic_quotes_keep_original_sentence_and_offsets():
    body = "😀 Intro.\n“We’re   walking.”"
    word = {"id": "w", "english": "walk", "meaning": "走", "source_hint": '''"We're walking."'''}
    resolve_vocabulary_sources({"body_en": body, "vocabulary": [word]})
    assert (
        word["source"]
        and body[word["source"]["word_start"] : word["source"]["word_end"]] == "walking"
    )
    assert word["source"]["quote"] == "“We’re   walking.”"


def test_verified_distinct_original_positions_survive_competing_senses():
    line = "Bank. Bank."
    words = [
        {
            "english": "bank",
            "meaning": meaning,
            "source": {"line_id": "a", "start": start, "end": start + 4, "quote": "Bank"},
        }
        for meaning, start in [("河岸", 0), ("银行", 6)]
    ]
    scene = normalize(
        SceneContent.model_validate(
            {"dialogue": [{"id": "a", "english": line}], "vocabulary": words}
        )
    )
    assert [w["source"]["start"] for w in scene["vocabulary"]] == [0, 6]


def test_malformed_irregular_and_nonword_derivatives_require_review():
    scene = normalize(
        SceneContent.model_validate(
            {
                "dialogue": [{"id": "a", "english": "Childs goed party successful."}],
                "vocabulary": [
                    {"english": "child"},
                    {"english": "go"},
                    {"english": "art"},
                    {"english": "success"},
                ],
            }
        )
    )
    assert all(w["source"] is None for w in scene["vocabulary"])


def test_verified_coordinates_resolve_ambiguous_form_but_otherwise_needs_review():
    from juya_api.listening_vocabulary import resolve_vocabulary_sources

    body = "We saw birds."
    hinted = {
        "english": "see",
        "id": "one",
        "meaning": "看",
        "source": {
            "start": 0,
            "end": 13,
            "quote": body,
            "word_start": 3,
            "word_end": 6,
            "word": "saw",
            "confirmed": True,
        },
    }
    unbound = {"english": "see", "id": "two", "meaning": "看"}
    resolve_vocabulary_sources({"body_en": body, "vocabulary": [hinted, unbound]})
    assert hinted["source"] and hinted["source"]["word"] == "saw"
    assert not unbound["source"] and unbound["source_reason"] == "source_ambiguous"


def test_derived_auto_source_never_changes_listening_import_identity():
    from copy import deepcopy

    from juya_api.listening_vocabulary import canonical_payload

    payload = {
        "body_en": "We ran.",
        "vocabulary": [
            {"id": "w", "english": "run", "meaning": "跑", "source": None, "source_hint": "We ran."}
        ],
    }
    resolved = deepcopy(payload)
    resolve_vocabulary_sources(resolved)
    assert resolved["vocabulary"][0]["source"]
    assert canonical_payload(payload) == canonical_payload(resolved)


def test_both_adapters_match_shared_client_source_examples():
    import json
    from pathlib import Path

    for case in json.loads(
        (Path(__file__).parent / "fixtures/vocabulary-matching-v1.json").read_text()
    ):
        word = {
            "id": "w",
            "english": case["term"],
            "meaning": "释义",
            "source_hint": case.get("hint", ""),
        }
        scene = normalize(
            SceneContent.model_validate(
                {"dialogue": [{"id": "a", "english": case["body"]}], "vocabulary": [word]}
            )
        )["vocabulary"][0]
        article = {"body_en": case["body"], "vocabulary": [dict(word)]}
        resolve_vocabulary_sources(article)
        listening = article["vocabulary"][0]
        if "reason" in case:
            assert scene["source_reason"] == listening["source_reason"] == case["reason"]
            assert scene["source"] is None and listening["source"] is None
        else:
            assert scene["source"]["quote"] == listening["source"]["word"] == case["quote"]
            assert scene["source"]["start"] == case["utf16"]
            assert listening["source"]["word_start"] == case["codepoint"]


def test_preview_and_publication_recompute_reliable_legacy_scene_source(admin, system):
    from juya_api.content_models import CardDraft

    from .content_helpers import draft, key, publish

    card = draft(admin)
    with system["sessions"].begin() as db:
        old = db.get(CardDraft, card["id"])
        body = old.payload
        words = [{**w, "source": None} for w in body["vocabulary"]]
        old.payload = {**body, "vocabulary": words}
    preview = admin.post(
        "/api/admin/v1/cards/" + card["id"] + "/preview",
        headers=key(),
        json={"revision": card["draft_revision"]},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["content"]["vocabulary"][0]["source"]["quote"] == "coffee"
    published = publish(admin, card)
    assert published["content"]["vocabulary"][0]["source"]["quote"] == "coffee"
