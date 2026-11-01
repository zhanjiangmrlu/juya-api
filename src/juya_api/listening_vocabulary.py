"""Exact source verification and stable semantic identities for optional vocabulary."""

import re


def sentence_spans(body):
    """Return original codepoint sentence spans, retaining punctuation and line boundaries."""
    return [
        (m.start(), m.end(), m.group()) for m in re.finditer(r"[^\s.!?][^.!?\r\n]*[.!?]?", body)
    ]


def vocabulary_errors(payload):
    """Validate each independent sense against its current original sentence and word."""
    body = payload.get("body_en", "")
    sentences = {(start, end, quote) for start, end, quote in sentence_spans(body)}
    ids = set()
    errors = []
    for word in payload.get("vocabulary", []):
        source = word.get("source")
        valid = bool(
            re.fullmatch(r"[A-Za-z]+(?:['’-][A-Za-z]+)*", word.get("english", "").strip())
            and word.get("id")
            and word["id"] not in ids
            and word.get("english", "").strip()
            and word.get("meaning", "").strip()
        )
        ids.add(word.get("id"))
        if source:
            start, end = source["word_start"], source["word_end"]
            valid = (
                valid
                and (source["start"], source["end"], source["quote"]) in sentences
                and source["start"] <= start < end <= source["end"]
                and body[start:end] == source["word"]
            )
            valid = valid and any(
                m.start() == start and m.end() == end
                for m in re.finditer(r"[A-Za-z]+(?:['’-][A-Za-z]+)*", body)
            )
            occurrences = list(
                re.finditer(r"\b" + re.escape(source["word"]) + r"\b", body, re.IGNORECASE)
            )
            if (
                source["word"].casefold() != word["english"].strip().casefold()
                or len(occurrences) != 1
            ):
                valid = valid and source.get("confirmed", False)
        else:
            valid = False
        if not valid:
            errors.append("vocabulary:" + str(word.get("id", "")) + ":source_confirmation_required")
    return errors


def canonical_payload(payload):
    """Keep no-word legacy v1 identity; v2 includes ordered senses without random IDs."""
    result = {**payload}
    words = result.pop("vocabulary", [])
    if words:
        result["vocabulary"] = [
            {
                key: value
                for key, value in word.items()
                if key not in {"id", "source", "source_hint"}
            }
            | {
                **(
                    {"source_hint": word.get("source_hint", "")}
                    if not word.get("source") and word.get("source_hint")
                    else {}
                ),
                "source": {
                    key: value
                    for key, value in (word.get("source") or {}).items()
                    if key != "confirmed"
                },
            }
            for word in words
        ]
        return {"canonical_version": 2, "payload": result}
    return result


def content_equal(first, second):
    """Treat absent and empty vocabulary as identical without changing historic payloads."""
    return {**first, "vocabulary": first.get("vocabulary", [])} == {
        **second,
        "vocabulary": second.get("vocabulary", []),
    }
