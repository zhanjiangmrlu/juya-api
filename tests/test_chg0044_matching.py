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


def test_hop_and_hope_participles_are_distinct_in_both_modules_and_scene_publication(admin):
    from .content_helpers import content, draft, key, publish

    payload = content(admin)
    for term, actual, valid in [
        ("hop", "hoping", False),
        ("hop", "hopping", True),
        ("hope", "hoping", True),
        ("hoping", "hop", False),
        ("hop", "hoped", False),
    ]:
        line = f"I am {actual}."
        payload["dialogue"][0]["english"] = line
        word = {"id": "w", "english": term, "meaning": "测试"}
        payload["vocabulary"] = [word]
        card = draft(admin, payload)
        scene = card["content"]["vocabulary"][0]
        article = {"body_en": line, "vocabulary": [dict(word)]}
        resolve_vocabulary_sources(article)
        listening = article["vocabulary"][0]
        if valid:
            assert listening["source"]["word"] == scene["source"]["quote"] == actual
            assert publish(admin, card)["status"] == "published"
        else:
            preview = admin.post(
                f"/api/admin/v1/cards/{card['id']}/preview", headers=key(), json={"revision": 1}
            )
            assert preview.status_code == 422
            assert scene["source_reason"] == listening["source_reason"] == "source_unmatched"
            assert scene["source"] is None and listening["source"] is None


def test_shared_hint_or_identical_old_position_cannot_disambiguate_bank_senses():
    line = "I went to the bank."
    for module in ("scene", "listening"):
        for with_hint in (True, False):
            words = []
            for term, meaning in [("bank", "银行"), ("bank", "河岸"), ("went", "去")]:
                word = {"english": term, "meaning": meaning}
                if with_hint:
                    word["source_hint"] = line
                elif term == "bank":
                    word["source"] = (
                        {"line_id": "a", "start": 14, "end": 18, "quote": "bank"}
                        if module == "scene"
                        else {
                            "start": 0,
                            "end": 19,
                            "quote": line,
                            "word_start": 14,
                            "word_end": 18,
                            "word": "bank",
                            "confirmed": True,
                        }
                    )
                words.append(word)
            if module == "scene":
                words = normalize(
                    SceneContent.model_validate(
                        {"dialogue": [{"id": "a", "english": line}], "vocabulary": words}
                    )
                )["vocabulary"]
            else:
                resolve_vocabulary_sources({"body_en": line, "vocabulary": words})
            assert all(
                w.get("source_reason") == "source_sense_conflict" and not w["source"]
                for w in words[:2]
            )
            assert words[2]["source"]


def test_explicit_bank_sense_is_kept_when_only_an_unhinted_other_sense_contends():
    line = "The bank is open."
    words = [
        {"english": "bank", "meaning": "银行", "source_hint": line},
        {"english": "bank", "meaning": "河岸"},
    ]
    resolve_vocabulary_sources({"body_en": line, "vocabulary": words})
    assert words[0]["source"]["word"] == "bank"
    assert words[1]["source"] is None and words[1]["source_reason"] == "source_sense_conflict"


def test_listening_final_publication_blocks_other_lemmas_participles(admin):
    from .content_helpers import key
    from .test_integration06 import A, article, category

    owner = category(admin)
    row = article(admin, owner["id"])
    for term, allowed in [("hop", False), ("hope", True)]:
        payload = {
            **row["payload"],
            "body_en": "I am hoping.",
            "vocabulary": [{"id": "word", "english": term, "meaning": "释义"}],
        }
        response = admin.put(
            f"{A}/articles/{row['id']}",
            headers=key(),
            json={"revision": row["revision"], "category_id": owner["id"], "payload": payload},
        )
        assert response.status_code == 200, response.text
        row = response.json()
        published = admin.post(
            f"{A}/articles/{row['id']}/publish", headers=key(), json={"revision": row["revision"]}
        )
        assert published.status_code == (200 if allowed else 422), published.text


def test_optional_listening_vocabulary_checks_meaning_even_after_auto_matching(admin):
    from .content_helpers import key
    from .test_integration06 import A, article, category

    row = article(admin, category(admin)["id"], [{"id": "r", "english": "rest", "meaning": "  "}])
    assert row["payload"]["vocabulary"][0]["source"]["word"] == "rest"
    result = admin.post(
        f"{A}/articles/{row['id']}/publish", headers=key(), json={"revision": row["revision"]}
    )
    assert result.status_code == 422 and "vocabulary:" in result.text
