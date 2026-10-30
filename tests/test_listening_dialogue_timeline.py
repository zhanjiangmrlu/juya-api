"""Dialogue layout labels stay visible without invented speech timestamps."""

import pytest

from juya_api.errors import DomainError
from juya_api.listening_timeline import align_words


def recognized(*words):
    return [
        {"word": word, "start_ms": n * 200, "end_ms": n * 200 + 150} for n, word in enumerate(words)
    ]


@pytest.mark.parametrize("separator", ["\n", "\n\n"])
def test_dialogue_headings_and_speakers_do_not_require_spoken_timestamps(separator):
    body = separator.join(
        ["Arriving and Decorating", "Zoe: Happy birthday, Nina!", "Nina: Thanks, Zoe."]
    )
    result = align_words(body, recognized("Happy", "birthday", "Nina", "Thanks", "Zoe"), 2000)
    assert [body[w["start"] : w["end"]] for w in result] == [
        "Happy",
        "birthday",
        "Nina",
        "Thanks",
        "Zoe",
    ]
    assert result[0]["start"] == body.index("Happy")
    assert [w["start_ms"] for w in result] == [0, 200, 400, 600, 800]


def test_dialogue_still_requires_every_spoken_word():
    body = "Arriving and Decorating\n\nZoe: Happy birthday, Nina!\n\nNina: Thanks, Zoe."
    with pytest.raises(DomainError) as exc:
        align_words(body, recognized("Happy", "birthday", "Thanks", "Zoe"), 2000)
    assert exc.value.code == "timeline_coverage_low"


def test_plain_prose_without_terminal_punctuation_is_not_a_layout_heading():
    with pytest.raises(DomainError) as exc:
        align_words("A quiet morning\nOpen the window.", recognized("Open", "the", "window"), 2000)
    assert exc.value.code == "timeline_coverage_low"


def test_colon_in_single_voice_prose_does_not_exempt_missing_words():
    with pytest.raises(DomainError) as exc:
        align_words("Remember: Drink some water.", recognized("Drink", "some", "water"), 2000)
    assert exc.value.code == "timeline_coverage_low"


def test_dialogue_continuation_without_punctuation_is_still_required():
    body = "Zoe: Come here.\nStay with me\nNina: Yes."
    with pytest.raises(DomainError) as exc:
        align_words(body, recognized("Come", "here", "Yes"), 2000)
    assert exc.value.code == "timeline_coverage_low"
