"""Published token references, licensed local data and revocable original-word speech."""

import json
from datetime import timedelta

import pytest

from .content_helpers import content, draft, key, publish, recording


def source(text, word, occurrence=0):
    """Build an exact UTF-16 fixture range independently of dictionary tokenization."""
    start = -1
    for _ in range(occurrence + 1):
        start = text.index(word, start + 1)
    begin = len(text[:start].encode("utf-16-le")) // 2
    return {"line_id": "line-1", "start": begin, "end": begin + len(word), "quote": word}


def scenario(admin, text="😀 went went.", meanings=("去了", "另一处含义")):
    payload = content(admin)
    payload["dialogue"][0]["english"] = text
    word = "went" if "went" in text else "read"
    payload["vocabulary"] = [
        {
            "id": f"word-{index}",
            "english": word,
            "meaning": meaning,
            "source": source(text, word, index),
        }
        for index, meaning in enumerate(meanings)
    ]
    return publish(admin, draft(admin, payload))


def reference(card, word="went", start=3, end=7, **extra):
    return {
        "version_id": card["current_version_id"],
        "word": word,
        "line_id": "line-1",
        "start": start,
        "end": end,
        **extra,
    }


def path(card):
    return f"/api/mini/v1/cards/{card['id']}/dictionary"


@pytest.fixture
def local_lexicon(system, tmp_path):
    target = tmp_path / "licensed-test-fixture.json"
    data = {
        "provider": "synthetic-test-fixture",
        "license": "Synthetic test data only; not production dictionary coverage",
        "entries": {
            "go": {"phonetic": "/ɡəʊ/", "definitions": [{"part_of_speech": "v.", "meaning": "去"}]},
            "mobile": {"definitions": [{"meaning": "移动的"}]},
        },
        "forms": {"went": "go"},
    }
    target.write_text(json.dumps(data), encoding="utf-8")
    system["settings"].dictionary_path = target
    return target, data


def test_exact_context_works_unconfigured_and_duplicate_spellings_keep_their_meanings(admin, mini):
    card = scenario(admin)
    first = mini.get(path(card), params=reference(card))
    assert first.status_code == 200, first.text
    assert first.json() == {
        "word": "went",
        "lemma": None,
        "phonetic": "",
        "source": "context",
        "definitions": [{"part_of_speech": "", "meaning": "去了"}],
        "speech_text": "went",
        "provider": "context",
    }
    second = mini.get(path(card), params=reference(card, start=8, end=12))
    assert second.json()["definitions"][0]["meaning"] == "另一处含义"


def test_empty_context_falls_back_to_explicit_lemma_without_copying_lemma_ipa(
    admin, mini, local_lexicon
):
    card = scenario(admin, meanings=("去了", " "))
    context = mini.get(path(card), params=reference(card)).json()
    assert context["source"] == "context" and context["lemma"] == "go"
    response = mini.get(path(card), params=reference(card, start=8, end=12))
    assert response.status_code == 200, response.text
    assert response.json() == {
        "word": "went",
        "lemma": "go",
        "phonetic": "",
        "source": "dictionary",
        "definitions": [{"part_of_speech": "v.", "meaning": "去"}],
        "speech_text": "went",
        "provider": "synthetic-test-fixture",
    }


def test_actual_missing_is_distinct_from_unconfigured_and_broken_data(
    admin, mini, system, local_lexicon
):
    card = scenario(admin, text="😀 went went. cats", meanings=("去了", " "))
    body = reference(card, word="cats", start=14, end=18)
    missing = mini.get(path(card), params=body)
    assert missing.status_code == 200, missing.text
    assert missing.json()["source"] == "missing"
    assert missing.json()["lemma"] is None
    assert missing.json()["definitions"] == []
    system["settings"].dictionary_path = None
    unavailable = mini.get(path(card), params=body)
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "dictionary_unavailable"
    target, data = local_lexicon
    data["entries"]["go"]["definitions"][0]["meaning"] = " "
    target.write_text(json.dumps(data), encoding="utf-8")
    system["settings"].dictionary_path = target
    assert mini.get(path(card), params=body).status_code == 503
    # Broken optional general data must not prevent a confirmed contextual definition.
    assert mini.get(path(card), params=reference(card)).json()["source"] == "context"


def test_full_token_boundaries_share_abbreviations_apostrophes_hyphens_and_utf16(
    admin, mini, local_lexicon
):
    text = "😀 went. Don't Let’s take-away U.S. e.g. Dr. today. abc123 abc_foo"
    card = scenario(admin, text=text, meanings=("去了",))
    for word in ["went", "Don't", "Let’s", "take-away", "U.S.", "e.g.", "Dr.", "today"]:
        span = source(text, word)
        response = mini.get(
            path(card), params=reference(card, word=word, start=span["start"], end=span["end"])
        )
        assert response.status_code == 200, (word, response.text)
    for body in [
        reference(card, start=2, end=6),
        reference(card, word="wen", start=3, end=6),
        reference(card, line_id="other-line"),
        reference(card, word="arbitrary", start=3, end=12),
        reference(card, word=".", start=7, end=8),
        reference(card, word="Don", start=9, end=12),
        reference(card, word="take", start=22, end=26),
    ]:
        assert mini.get(path(card), params=body).status_code == 422
    for word in ["abc", "foo"]:
        span = source(text, word)
        assert (
            mini.get(
                path(card), params=reference(card, word=word, start=span["start"], end=span["end"])
            ).status_code
            == 422
        )


def test_context_requires_unique_exact_source_and_never_guesses_by_spelling(
    admin, mini, system, local_lexicon
):
    from juya_api.content_models import CardVersion

    card = scenario(admin)
    with system["sessions"].begin() as db:
        version = db.get(CardVersion, card["current_version_id"])
        payload = dict(version.payload)
        payload["vocabulary"] = [dict(word) for word in payload["vocabulary"]]
        # Legacy ambiguous saved data cannot authorize a guessed contextual meaning.
        payload["vocabulary"][1]["source"] = payload["vocabulary"][0]["source"]
        version.payload = payload
    result = mini.get(path(card), params=reference(card)).json()
    assert result["source"] == "dictionary"
    assert result["definitions"][0]["meaning"] == "去"


def test_dictionary_and_speech_reject_other_role_stale_version_and_offline(admin, mini):
    card = scenario(admin)
    body = reference(card)
    authorization = mini.headers.pop("Authorization")
    assert mini.get(path(card), params=body).status_code == 401
    assert mini.post(path(card) + "/pronunciation", json=body, headers=key()).status_code == 401
    mini.headers["Authorization"] = authorization
    assert admin.get(path(card).replace("/mini/", "/admin/"), params=body).status_code == 404
    assert mini.get(path(card), params=body | {"version_id": "another-version"}).status_code == 409
    assert (
        mini.post(
            path(card) + "/pronunciation", json=body | {"word": "anything"}, headers=key()
        ).status_code
        == 422
    )
    admin.post(
        f"/api/admin/v1/cards/{card['id']}/offline",
        json={"revision": card["draft_revision"]},
        headers=key(),
    )
    assert mini.get(path(card), params=body).status_code == 410
    assert mini.post(path(card) + "/pronunciation", json=body, headers=key()).status_code == 410


def test_original_word_speech_uses_existing_jobs_budget_cache_and_live_grants(
    admin, mini, system, local_lexicon
):
    from juya_api.worker import run_job

    card = scenario(admin, meanings=("", ""))
    body = reference(card)
    speech = path(card) + "/pronunciation"
    before = mini.get(speech, params=body)
    assert before.status_code == 200, before.text
    assert before.json()["state"] == "missing"
    headers = key()
    first = mini.post(speech, json=body, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["state"] == "processing"
    assert mini.post(speech, json=body, headers=headers).json()["job_id"] == first.json()["job_id"]
    assert mini.post(speech, json=body, headers=key()).json()["job_id"] == first.json()["job_id"]
    assert mini.post(speech, json=body | {"text": "go"}, headers=key()).status_code == 422
    calls = []

    class Speech:
        def synthesize(self, text, configuration, session_id):
            calls.append(text)
            return recording()

    run_job(
        system["settings"],
        system["sessions"],
        first.json()["job_id"],
        clock=mini.app.state.clock,
        tts=Speech(),
    )
    assert calls == ["went"]
    ready = mini.get(speech, params=body)
    assert ready.json()["state"] == "ready", ready.text
    url = ready.json()["url"]
    assert mini.get(url, headers={"Range": "bytes=0-15"}).status_code == 206
    from sqlalchemy import select

    from juya_api.pronunciation_models import Pronunciation

    with system["sessions"]() as db:
        row = db.scalar(select(Pronunciation))
        assert row.reading == row.spelling == "went"
    # Another login cannot use the original session's grant.
    login = mini.post(
        "/api/mini/v1/auth/wechat",
        headers=key(),
        json={"code": "bob:dict", "consent": True, "consent_version": "2026-10-17"},
    )
    alice = mini.headers["Authorization"]
    mini.headers["Authorization"] = "Bearer " + login.json()["access_token"]
    assert mini.get(url).status_code == 401
    mini.headers["Authorization"] = alice
    system["time"][0] += timedelta(minutes=5)
    assert mini.get(url).status_code == 401
    fresh_url = mini.get(speech, params=body).json()["url"]
    admin.post(
        f"/api/admin/v1/cards/{card['id']}/offline",
        headers=key(),
        json={"revision": card["draft_revision"]},
    )
    assert mini.get(fresh_url).status_code == 410


def test_exact_original_context_reading_separates_homograph_cache_and_lemma_never_replaces_original(
    admin, mini, system
):
    from sqlalchemy import select

    from juya_api.content_models import CardVersion
    from juya_api.pronunciation_models import Pronunciation

    card = scenario(admin, text="read read.", meanings=("过去读过", "现在读"))
    with system["sessions"].begin() as db:
        version = db.get(CardVersion, card["current_version_id"])
        payload = dict(version.payload)
        payload["vocabulary"] = [dict(word) for word in payload["vocabulary"]]
        payload["vocabulary"][0]["pronunciation_text"] = "red"
        version.payload = payload
    first = reference(card, word="read", start=0, end=4)
    second = reference(card, word="read", start=5, end=9)
    assert mini.get(path(card), params=first).json()["speech_text"] == "red"
    assert mini.get(path(card), params=second).json()["speech_text"] == "read"
    jobs = [
        mini.post(path(card) + "/pronunciation", json=body, headers=key()).json()
        for body in [first, second]
    ]
    assert jobs[0]["job_id"] != jobs[1]["job_id"]
    with system["sessions"]() as db:
        assert set(db.scalars(select(Pronunciation.reading))) == {"red", "read"}


def test_lexicon_requires_real_metadata_and_nonempty_definitions(tmp_path):
    from juya_api.config import Settings
    from juya_api.dictionary import LocalDictionary
    from juya_api.errors import DomainError

    data = {"provider": "", "license": "", "entries": {"go": {"definitions": [{"meaning": "去"}]}}}
    target = tmp_path / "invalid.json"
    target.write_text(json.dumps(data), encoding="utf-8")
    settings = Settings(
        database_url="sqlite:///:memory:",
        field_encryption_key="yK1Xc0sWCxUQxXvHPEgY46iVE1mW6BwJqHWSeg1oEJ4=",
        lookup_key="test-dictionary-at-least32characters",
        dictionary_path=target,
    )
    with pytest.raises(DomainError, match="dictionary_unavailable"):
        LocalDictionary(settings).lookup("go")


def test_local_data_casefold_reload_and_invalid_replacement_never_returns_old_dictionary(
    local_lexicon, system
):
    from juya_api.dictionary import LocalDictionary
    from juya_api.errors import DomainError

    target, data = local_lexicon
    gateway = LocalDictionary(system["settings"])
    assert gateway.lookup("WENT").definitions[0].meaning == "去"
    data["entries"]["GO"] = data["entries"].pop("go")
    data["entries"]["GO"]["definitions"][0]["meaning"] = "前往另一个地方"
    data["forms"] = {"Went": "GO"}
    target.write_text(json.dumps(data), encoding="utf-8")
    assert gateway.lookup("wEnT").definitions[0].meaning == "前往另一个地方"
    assert gateway.lookup("wEnT").lemma == "GO"
    target.write_text('{"provider":', encoding="utf-8")
    with pytest.raises(DomainError, match="dictionary_unavailable"):
        gateway.lookup("went")


def test_lemma_context_never_copies_lemma_reading_or_phonetic_to_clicked_word(admin, mini, system):
    from juya_api.content_models import CardVersion

    card = scenario(admin)
    with system["sessions"].begin() as db:
        version = db.get(CardVersion, card["current_version_id"])
        payload = dict(version.payload)
        payload["vocabulary"] = [dict(word) for word in payload["vocabulary"]]
        payload["vocabulary"][0].update(english="go", phonetic="/ɡəʊ/", pronunciation_text="go")
        version.payload = payload
    result = mini.get(path(card), params=reference(card)).json()
    assert result["definitions"][0]["meaning"] == "去了"
    assert result["word"] == result["speech_text"] == "went"
    assert result["phonetic"] == ""


def test_speech_grants_reject_other_purpose_old_version_tampering_and_logout(admin, mini, system):
    from juya_api.worker import run_job

    card = scenario(admin)
    body = reference(card)
    voice = path(card) + "/pronunciation"
    accepted = mini.post(voice, json=body, headers=key()).json()

    class Speech:
        def synthesize(self, *_):
            return recording()

    run_job(
        system["settings"],
        system["sessions"],
        accepted["job_id"],
        clock=mini.app.state.clock,
        tts=Speech(),
    )
    url = mini.get(voice, params=body).json()["url"]
    assert mini.get(url + "broken").status_code == 401
    word_url = f"/api/mini/v1/cards/{card['id']}/words/word-0/pronunciation"
    vocabulary_grant = mini.get(word_url, params={"version_id": body["version_id"]}).json()["url"]
    wrong_purpose = "/api/mini/v1/dictionary-pronunciation/" + vocabulary_grant.rsplit("/", 1)[1]
    assert mini.get(wrong_purpose).status_code == 401
    changed = admin.put(
        f"/api/admin/v1/cards/{card['id']}",
        headers=key(),
        json={
            "revision": card["draft_revision"],
            "content": {**card["content"], "name": "更新的词典测试卡"},
        },
    )
    assert changed.status_code == 200, changed.text
    updated = publish(admin, changed.json())
    assert updated["current_version_id"] != body["version_id"]
    assert mini.get(url).status_code == 409
    body["version_id"] = updated["current_version_id"]
    fresh = mini.get(voice, params=body).json()["url"]
    authorization = mini.headers.pop("Authorization")
    # Native audio uses the opaque grant while its originating session is still active.
    assert mini.get(fresh).status_code == 200
    mini.headers["Authorization"] = authorization
    assert mini.post("/api/mini/v1/auth/logout", headers=key()).status_code == 200
    mini.headers.pop("Authorization")
    assert mini.get(fresh).status_code == 401


def test_dictionary_speech_reuses_provider_attempt_budget_and_retry_cooldown(admin, mini, system):
    from juya_api.errors import DomainError
    from juya_api.worker import run_job

    card = scenario(admin)
    body = reference(card)
    voice = path(card) + "/pronunciation"
    system["settings"].tts_daily_budget = 1
    accepted = mini.post(voice, json=body, headers=key()).json()
    calls = []

    class UnavailableSpeech:
        def synthesize(self, text, *_):
            calls.append(text)
            raise DomainError(503, "tts_temporary", "发音暂不可用")

    run_job(
        system["settings"],
        system["sessions"],
        accepted["job_id"],
        clock=mini.app.state.clock,
        tts=UnavailableSpeech(),
    )
    system["time"][0] += timedelta(seconds=11)
    run_job(
        system["settings"],
        system["sessions"],
        accepted["job_id"],
        clock=mini.app.state.clock,
        tts=UnavailableSpeech(),
    )
    assert calls == ["went"]
    failed = mini.get(voice, params=body).json()
    assert failed["state"] == "failed"
    assert failed["error_code"] == "tts_budget_exceeded"
    assert mini.post(voice, json=body, headers=key()).status_code == 429


@pytest.mark.parametrize("non_ascii", ["İ", "ı", "ſ", "K"])
def test_python_casefold_cannot_authorize_tokens_absent_from_javascript_tokenizer(
    admin, mini, local_lexicon, non_ascii
):
    text = "😀 went. " + non_ascii
    card = scenario(admin, text=text, meanings=("去了",))
    span = source(text, non_ascii)
    body = reference(card, word=non_ascii, start=span["start"], end=span["end"])
    response = mini.get(path(card), params=body)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "dictionary_reference_invalid"
    assert mini.post(path(card) + "/pronunciation", json=body, headers=key()).status_code == 422


def ready_speech(admin, mini, system):
    """Prepare validated audio through the real job runner with only cloud synthesis replaced."""
    from juya_api.worker import run_job

    card = scenario(admin)
    body = reference(card)
    voice = path(card) + "/pronunciation"
    accepted = mini.post(voice, json=body, headers=key())
    assert accepted.status_code == 200, accepted.text

    class Speech:
        def synthesize(self, *_):
            return recording()

    run_job(
        system["settings"],
        system["sessions"],
        accepted.json()["job_id"],
        clock=mini.app.state.clock,
        tts=Speech(),
    )
    return voice, body


def test_new_session_for_same_user_cannot_reuse_previous_sessions_speech_grant(admin, mini, system):
    voice, body = ready_speech(admin, mini, system)
    original = mini.get(voice, params=body).json()["url"]
    old_session = mini.headers["Authorization"]
    login = mini.post(
        "/api/mini/v1/auth/wechat",
        headers=key(),
        json={
            "code": "alice:dictionary-new-session",
            "consent": True,
            "consent_version": "2026-10-17",
        },
    )
    assert login.status_code == 200, login.text
    mini.headers["Authorization"] = "Bearer " + login.json()["access_token"]
    assert mini.headers["Authorization"] != old_session
    rejected = mini.get(original)
    assert rejected.status_code == 401
    assert rejected.json()["error"]["code"] == "speech_session_expired"
    fresh = mini.get(voice, params=body).json()["url"]
    assert mini.get(fresh).status_code == 200
    # Logging in on another device does not revoke the still-valid original session.
    mini.headers["Authorization"] = old_session
    assert mini.get(original).status_code == 200


def test_natural_session_expiry_revokes_a_grant_before_its_own_five_minute_expiry(
    admin, mini, system
):
    voice, body = ready_speech(admin, mini, system)
    system["time"][0] += timedelta(days=7, minutes=-1)
    response = mini.get(voice, params=body)
    assert response.status_code == 200, response.text
    near_expiry = response.json()["url"]
    assert mini.get(near_expiry).status_code == 200
    system["time"][0] += timedelta(minutes=1)
    rejected = mini.get(near_expiry)
    assert rejected.status_code == 401
    assert rejected.json()["error"]["code"] == "speech_session_expired"
