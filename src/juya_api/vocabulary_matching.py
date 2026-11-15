"""Shared deterministic inflection matching on original source coordinates."""

import re
from functools import lru_cache

IRREGULAR_FORMS = {
    "good": "better best",
    "well": "better best",
    "bad": "worse worst",
    "far": "farther farthest further furthest",
    "fly": "flies flew flown flying",
    "swim": "swam swum swimming",
    "drive": "drove driven driving",
    "build": "built building",
    "catch": "caught catching",
    "teach": "taught teaching",
    "study": "studies studied studying",
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


COMPARABLE = set(
    [
        "fast",
        "slow",
        "quick",
        "short",
        "long",
        "old",
        "young",
        "high",
        "low",
        "deep",
        "light",
        "dark",
        "warm",
        "cold",
        "large",
        "small",
        "tall",
        "nice",
        "fine",
        "safe",
        "brave",
        "big",
        "hot",
        "thin",
        "sad",
        "wet",
        "fat",
        "happy",
        "easy",
        "busy",
        "early",
        "heavy",
        "close",
        "clean",
        "hard",
        "rich",
        "poor",
        "bright",
        "quiet",
        "strong",
        "weak",
        "late",
        "great",
    ]
)


@lru_cache(maxsize=4096)
def word_forms(english):
    """生成可自动对应的常见词形；english 为文档中的英文词条"""
    base = english.strip().casefold().replace("’", "'")
    if base in IRREGULAR_FORMS:
        forms = {base, *IRREGULAR_FORMS[base].split()}
        if base not in {
            "good",
            "bad",
            "well",
            "far",
            "be",
            "have",
            "do",
            "go",
            "child",
            "person",
            "man",
            "woman",
            "foot",
            "tooth",
            "mouse",
        }:
            plural = (
                base[:-1] + "ies"
                if re.search(r"[^aeiou]y$", base)
                else base + ("es" if re.search(r"(?:s|x|z|ch|sh|o)$", base) else "s")
            )
            forms.add(plural)
            if not any(word.endswith("ing") for word in forms):
                forms.add(base + "ing")
        return forms
    forms = {base, base + "s"}
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
    if base in COMPARABLE:
        if re.search(r"[^aeiou]y$", base):
            forms.update({base[:-1] + "ier", base[:-1] + "iest"})
        elif base.endswith("e"):
            forms.update({base + "r", base + "st"})
        else:
            stem = base + base[-1] if base in {"big", "hot", "thin", "sad", "wet", "fat"} else base
            forms.update({stem + "er", stem + "est"})
    return forms


def normalized_quote(quote):
    """仅归一化排版空白与弯引号；quote 为文档原句或正文原句"""
    return " ".join(quote.casefold().translate(str.maketrans("‘’“”", "''\"\"")).split())


TOKEN = re.compile(r"(?<!\w)[A-Za-z]+(?:['’‘\-‑][A-Za-z]+)*(?!\w)")
AMBIGUOUS = {"better", "best", "saw", "found", "left", "felt"}


def matching_spans(text, english):
    """Compare full tokens bidirectionally, always yielding offsets in original text."""
    term = normalized_quote(english).strip()
    if not term:
        return
    if not TOKEN.fullmatch(term):
        pattern = r"(?<!\w)" + r"\s+".join(re.escape(piece) for piece in term.split()) + r"(?!\w)"
        pattern = pattern.replace("'", "['’‘]").replace(r"\-", "[-‑]")
        for match in re.finditer(pattern, text, re.I):
            yield match.span()
        return
    for match in TOKEN.finditer(text):
        actual = normalized_quote(match.group()).replace("‑", "-")
        if actual == term or actual in word_forms(term) or term in word_forms(actual):
            yield match.span()


def resolve_words(words, candidates):
    """Keep a validated explicit position; competing senses without evidence need review."""
    positions: dict[tuple, list] = {}
    for word in words:
        hint = word.get("source_hint", "")
        old = word.get("source")
        choices, hint_exists = candidates(word)
        chosen = next(
            (
                c
                for c in choices
                if old and all(old.get(k) == v for k, v in c.items() if k != "confirmed")
            ),
            None,
        )
        explicit_position = chosen is not None
        reliable = [
            c
            for c in choices
            if hint
            or (
                normalized_quote(word["english"]) not in AMBIGUOUS
                and normalized_quote(c.get("word", c["quote"])) not in AMBIGUOUS
            )
        ]
        chosen = chosen or next(iter(reliable), None)
        word["source"] = chosen
        word.pop("source_reason", None)
        if chosen:
            position = (
                normalized_quote(word["english"]),
                chosen.get("line_id"),
                chosen.get("word_start", chosen["start"]),
                chosen.get("word_end", chosen["end"]),
            )
            positions.setdefault(position, []).append((word, bool(hint) or explicit_position))
        else:
            word["source_reason"] = (
                "source_hint_conflict"
                if hint and not hint_exists
                else "source_ambiguous"
                if choices and not reliable
                else "source_unmatched"
            )
    for group in positions.values():
        if len({w.get("meaning", "") for w, _ in group}) > 1:
            for word, evidence in group:
                if not evidence:
                    word["source"] = None
                    word["source_reason"] = "source_sense_conflict"
