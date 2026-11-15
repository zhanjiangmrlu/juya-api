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
    "begin": "began begun beginning",
    "forget": "forgot forgotten forgetting",
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


# These verbs retain the inflection of their root, unlike nouns such as "logo".
COMPOUND_VERB_ROOTS = {
    "forego": "go",
    "forgo": "go",
    "outgo": "go",
    "undergo": "go",
    "misdo": "do",
    "outdo": "do",
    "overdo": "do",
    "redo": "do",
    "underdo": "do",
    "undo": "do",
}

# Most nouns ending in -o take -s. These common exceptions take -es or allow both.
O_ES = {"echo", "embargo", "hero", "potato", "tomato", "veto"}
O_S_OR_ES = {
    "buffalo",
    "cargo",
    "domino",
    "flamingo",
    "mango",
    "mosquito",
    "tornado",
    "torpedo",
    "volcano",
}

# Regular multisyllable verbs usually keep their final consonant, as in "answered".
# A stressed final syllable accounts for the double consonant in these exceptions.
STRESSED_FINAL = {
    "admit",
    "commit",
    "compel",
    "concur",
    "confer",
    "control",
    "defer",
    "demur",
    "deter",
    "emit",
    "equip",
    "excel",
    "expel",
    "impel",
    "incur",
    "infer",
    "occur",
    "omit",
    "patrol",
    "permit",
    "prefer",
    "propel",
    "rebel",
    "recur",
    "refer",
    "regret",
    "remit",
    "repel",
    "submit",
    "transfer",
    "transmit",
}


@lru_cache(maxsize=4096)
def word_forms(english):
    """生成可自动对应的常见词形；english 为文档中的英文词条"""
    base = english.strip().casefold().replace("’", "'")
    root = COMPOUND_VERB_ROOTS.get(base)
    if root:
        prefix = base.removesuffix(root)
        return {prefix + form for form in word_forms(root)}
    consonant_y = bool(re.search(r"[^aeiou]y$", base))
    if consonant_y:
        plural = base[:-1] + "ies"
    elif re.search(r"(?:s|x|z|ch|sh)$", base) or base in O_ES:
        plural = base + "es"
    else:
        plural = base + "s"
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
            forms.add(plural)
            if not any(word.endswith("ing") for word in forms):
                forms.add(base + "ing")
        return forms
    forms = {base, plural}
    if base in O_S_OR_ES:
        forms.add(base + "es")
    if base.endswith("ie"):
        forms.update({base + "d", base[:-2] + "ying"})
    elif base.endswith("e"):
        forms.update({base + "d", base[:-1] + "ing"})
    elif consonant_y:
        forms.update({base[:-1] + "ied", base + "ing"})
    else:
        short_vowel = re.fullmatch(r"[^aeiou]*[aeiou][bcdfgklmnprstvz]", base)
        stem = base + base[-1] if short_vowel or base in STRESSED_FINAL else base
        forms.update({stem + "ed", stem + "ing"})
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
        has_position = chosen is not None
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
            positions.setdefault(position, []).append((word, bool(hint) or has_position))
        else:
            word["source_reason"] = (
                "source_hint_conflict"
                if hint and not hint_exists
                else "source_ambiguous"
                if choices and not reliable
                else "source_unmatched"
            )
    for group in positions.values():
        senses = {word.get("meaning", "").strip() for word, _ in group}
        if len(senses) < 2:
            continue
        supported = {
            word.get("meaning", "").strip() for word, has_evidence in group if has_evidence
        }
        for word, _ in group:
            if supported != {word.get("meaning", "").strip()}:
                word["source"] = None
                word["source_reason"] = "source_sense_conflict"
