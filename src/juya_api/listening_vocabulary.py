"""Exact source verification and stable semantic identities for optional vocabulary."""

import re


def sentence_spans(body):
    """Return original codepoint sentence spans, retaining punctuation and line boundaries."""
    return [
        (m.start(), m.end(), m.group()) for m in re.finditer(r"[^\s.!?][^.!?\r\n]*[.!?]?", body)
    ]


# 仅采用常见明确变形；不能确定的词形保留原句提示，不生成虚构位置
IRREGULAR_FORMS = {
    "be": "am is are was were been being",
    "go": "goes went gone going",
    "do": "does did done doing",
    "have": "has had having",
    "make": "made making",
    "take": "took taken taking",
    "get": "got gotten getting",
    "come": "came coming",
    "see": "saw seen seeing",
    "say": "said saying",
    "give": "gave given giving",
    "find": "found finding",
    "think": "thought thinking",
    "know": "knew known knowing",
    "write": "wrote written writing",
    "read": "reading",
    "run": "ran running",
    "eat": "ate eaten eating",
    "drink": "drank drunk drinking",
    "buy": "bought buying",
    "bring": "brought bringing",
    "speak": "spoke spoken speaking",
    "leave": "left leaving",
    "feel": "felt feeling",
    "keep": "kept keeping",
    "sleep": "slept sleeping",
    "child": "children",
    "person": "people",
    "man": "men",
    "woman": "women",
    "foot": "feet",
    "tooth": "teeth",
    "mouse": "mice",
}


def word_forms(english):
    """生成可自动对应的常见词形；english 为文档中的英文词条"""
    base = english.strip().casefold().replace("’", "'")
    forms = {base, base + "s"}
    forms.update(IRREGULAR_FORMS.get(base, "").split())
    if re.search(r"(?:s|x|z|ch|sh|o)$", base):
        forms.add(base + "es")
    if re.search(r"[^aeiou]y$", base):
        forms.update({base[:-1] + "ies", base[:-1] + "ied"})
    if base.endswith("e"):
        forms.update({base + "d", base[:-1] + "ing"})
    else:
        forms.update({base + "ed", base + "ing"})
    if re.search(r"[^aeiou][aeiou][^aeiouwxy]$", base):
        forms.update({base + base[-1] + "ed", base + base[-1] + "ing"})
    if base.endswith("ie"):
        forms.add(base[:-2] + "ying")
    return forms


def normalized_quote(quote):
    """仅归一化排版空白与弯引号；quote 为文档原句或正文原句"""
    return " ".join(quote.translate(str.maketrans("‘’“”", "''\"\"")).split())


def resolve_source(body, word):
    """根据原句定位真实词形；body 为当前正文，word 为独立词条及文档原句"""
    old = word.get("source")
    if old and not vocabulary_errors({"body_en": body, "vocabulary": [word]}):
        return old
    hint = word.get("source_hint") or (old or {}).get("quote", "")
    sentences = sentence_spans(body)
    if hint:
        sentences = [
            span for span in sentences if normalized_quote(span[2]) == normalized_quote(hint)
        ]
    forms = word_forms(word.get("english", ""))
    candidates = []
    for start, end, quote in sentences:
        tokens = list(re.finditer(r"[A-Za-z]+(?:['’-][A-Za-z]+)*", quote))
        exact = [
            token
            for token in tokens
            if token.group().casefold() == word["english"].strip().casefold()
        ]
        matches = exact or [
            token for token in tokens if token.group().casefold().replace("’", "'") in forms
        ]
        # 原句含多个不同变形且没有原词时无法确定义项，不自动猜选
        if not matches or len({token.group().casefold() for token in matches}) > 1:
            continue
        for token in matches:
            candidates.append(
                {
                    "start": start,
                    "end": end,
                    "quote": quote,
                    "word_start": start + token.start(),
                    "word_end": start + token.end(),
                    "word": token.group(),
                    "confirmed": True,
                }
            )
    # 文档已经给出原句时，相同句子/词形重复出现可使用第一处真实位置
    return candidates[0] if candidates and (hint or len(candidates) == 1) else None


def resolve_vocabulary_sources(payload):
    """补齐保存资料的真实原句位置；payload 为当前听读草稿或导入资料"""
    body = payload.get("body_en", "")
    for word in payload.get("vocabulary", []):
        old = word.get("source")
        source = resolve_source(body, word)
        if old and not source and not word.get("source_hint"):
            word["source_hint"] = old["quote"]
        word["source"] = source


def vocabulary_errors(payload):
    """校验真实原句及完整词形位置；payload 为待发布听读资料，不要求人工确认标记"""
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
