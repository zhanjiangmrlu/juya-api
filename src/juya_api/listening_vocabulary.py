"""Exact source verification and stable semantic identities for optional vocabulary."""

import re


def sentence_spans(body):
    """Return original codepoint sentence spans, retaining punctuation and line boundaries."""
    return [
        (m.start(), m.end(), m.group())
        for m in re.finditer(r"""[^\s.!?][^.!?\r\n]*[.!?]*[”“’"']*""", body)
    ]


def canonical_payload(payload):
    """Keep no-word v1 hashes; v3 excludes derived matches and preserves unresolved source hints."""
    result = {**payload}
    words = result.pop("vocabulary", [])
    if words:
        result["vocabulary"] = [
            {
                key: value
                for key, value in word.items()
                if key not in {"id", "source", "source_reason", "source_hint"}
            }
            | ({"source_hint": word["source_hint"]} if word.get("source_hint") else {})
            for word in words
        ]
        return {"canonical_version": 3, "payload": result}
    return result


def content_equal(first, second):
    """Treat absent and empty vocabulary as identical without changing historic payloads."""
    return {**first, "vocabulary": first.get("vocabulary", [])} == {
        **second,
        "vocabulary": second.get("vocabulary", []),
    }


def resolve_vocabulary_sources(payload):
    """Bind the saved hearing vocabulary using original Unicode codepoint spans."""
    from .vocabulary_matching import matching_spans, normalized_quote, resolve_words

    spans = sentence_spans(payload.get("body_en", ""))

    def candidates(word):
        hint = normalized_quote(word.get("source_hint", ""))
        rows = [s for s in spans if not hint or normalized_quote(s[2]) == hint]
        choices = []
        for start, end, quote in rows:
            for left, right in matching_spans(quote, word["english"]):
                choices.append(
                    {
                        "start": start,
                        "end": end,
                        "quote": quote,
                        "word_start": start + left,
                        "word_end": start + right,
                        "word": quote[left:right],
                        "confirmed": True,
                    }
                )
        return choices, bool(rows)

    def manual_source(word):
        """Validate a manual sentence and codepoint fragment without inflection rules."""
        source = word.get("source")
        if (
            not source
            or not source.get("confirmed")
            or normalized_quote(source.get("manual_english") or "")
            != normalized_quote(word["english"])
            or not word["english"].strip()
        ):
            return None
        if (source["start"], source["end"], source["quote"]) not in spans:
            return None
        if not source["start"] <= source["word_start"] < source["word_end"] <= source["end"]:
            return None
        actual = payload["body_en"][source["word_start"] : source["word_end"]]
        return dict(source) if actual.strip() and actual == source["word"] else None

    resolve_words(payload.get("vocabulary", []), candidates, manual_source)


def vocabulary_errors(payload):
    from copy import deepcopy

    from .vocabulary_matching import TOKEN

    checked = deepcopy(payload)
    resolve_vocabulary_sources(checked)
    seen = set()
    errors = []
    for word in checked.get("vocabulary", []):
        identifier = word.get("id")
        if (
            not identifier
            or identifier in seen
            or not TOKEN.fullmatch(word.get("english", "").strip())
            or not word.get("meaning", "").strip()
            or not word.get("source")
        ):
            errors.append(f"vocabulary:{identifier or ''}:source_confirmation_required")
        seen.add(identifier)
    return errors
