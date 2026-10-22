"""Exact published English-token references and explicitly licensed local lexical data."""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from types import MappingProxyType
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .content_service import published_card
from .errors import DomainError
from .pronunciation import configuration
from .security import fingerprint

# Keep this expression and ASCII-neighbor rule identical to the mini-program tokenizer.
TOKEN_PATTERN = (
    r"(?:[A-Za-z]+\.){2,}|(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|vs|etc)\."
    r"|[A-Za-z]+(?:['’\-][A-Za-z]+)*"
)
TOKENS = re.compile(TOKEN_PATTERN, re.I | re.ASCII)
ASCII_NEIGHBOR = re.compile(r"[A-Za-z0-9_]", re.I | re.ASCII)


class DictionaryReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version_id: str = Field(min_length=1, max_length=36)
    word: str = Field(min_length=1, max_length=300)
    line_id: str = Field(min_length=1, max_length=64)
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def ordered_range(self):
        if self.end <= self.start:
            raise ValueError("请选择正文中完整的英文单词")
        return self


class Definition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    part_of_speech: str = Field(default="", max_length=80)
    meaning: str = Field(min_length=1, max_length=10000)

    @field_validator("meaning", "part_of_speech")
    @classmethod
    def trim_text(cls, value: str, info):
        value = value.strip()
        if info.field_name == "meaning" and not value:
            raise ValueError("词典释义不能为空")
        return value


class LexicalResult(BaseModel):
    lemma: str | None = None
    phonetic: str = ""
    definitions: list[Definition] = Field(default_factory=list)
    provider: str


class DictionaryResult(LexicalResult):
    word: str
    source: Literal["context", "dictionary", "missing"]
    speech_text: str


class LexiconEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    phonetic: str = Field(default="", max_length=300)
    definitions: list[Definition] = Field(min_length=1, max_length=32)


class LexiconData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    provider: str = Field(min_length=1, max_length=300)
    license: str = Field(min_length=1, max_length=10000)
    entries: dict[str, LexiconEntry]
    forms: dict[str, str] = Field(default_factory=dict)

    @field_validator("provider", "license")
    @classmethod
    def required_metadata(cls, value: str):
        if not value.strip():
            raise ValueError("必须提供词典来源和授权说明")
        return value.strip()

    @model_validator(mode="after")
    def explicit_forms(self):
        keys = list(self.entries)
        forms = list(self.forms)
        if any(not TOKENS.fullmatch(value) for value in [*keys, *forms, *self.forms.values()]):
            raise ValueError("词典索引必须是完整英文词项")
        if len(set(key.casefold() for key in keys)) != len(keys) or len(
            set(key.casefold() for key in forms)
        ) != len(forms):
            raise ValueError("词典索引不能大小写重复")
        entries = {key.casefold() for key in keys}
        if any(value.casefold() not in entries for value in self.forms.values()):
            raise ValueError("原形映射必须指向已提供的词条")
        return self


class DictionaryGateway(Protocol):
    def lookup(self, word: str) -> LexicalResult: ...


@dataclass(frozen=True)
class LexiconIndex:
    provider: str
    entries: Mapping[str, LexiconEntry]
    forms: Mapping[str, str]


class LocalDictionary:
    """Load an operator-supplied JSON file; metadata is declared, not a license audit."""

    def __init__(self, settings):
        self.settings = settings
        self._lock = Lock()
        self._signature: tuple[Path, int, int] | None = None
        self._data: LexiconIndex | None = None

    def _load(self) -> LexiconIndex:
        with self._lock:
            try:
                path = self.settings.dictionary_path
                if path is None:
                    raise ValueError("unconfigured")
                info = path.stat()
                signature = (path, info.st_mtime_ns, info.st_size)
                if signature != self._signature:
                    with path.open("rb") as stream:
                        raw = stream.read(64 * 1024 * 1024 + 1)
                    if len(raw) > 64 * 1024 * 1024:
                        raise ValueError("oversized dictionary")
                    value = LexiconData.model_validate(json.loads(raw))
                    indexed = LexiconIndex(
                        provider=value.provider,
                        entries=MappingProxyType(
                            {key.casefold(): entry for key, entry in value.entries.items()}
                        ),
                        forms=MappingProxyType(
                            {key.casefold(): lemma for key, lemma in value.forms.items()}
                        ),
                    )
                    self._data, self._signature = indexed, signature
                assert self._data is not None
                return self._data
            except (OSError, ValueError, ValidationError):
                raise DomainError(
                    503, "dictionary_unavailable", "词典服务暂不可用，请重试"
                ) from None

    def lookup(self, word: str) -> LexicalResult:
        data = self._load()
        spelling = word.casefold()
        lemma = data.forms.get(spelling)
        exact = data.entries.get(spelling)
        selected = exact or (data.entries.get(lemma.casefold()) if lemma else None)
        return LexicalResult(
            lemma=lemma if lemma and lemma.casefold() != spelling else None,
            # A lemma's IPA must never appear as the clicked word's IPA.
            phonetic=exact.phonetic.strip() if exact else "",
            definitions=list(selected.definitions) if selected else [],
            provider=data.provider,
        )


@dataclass(frozen=True)
class TokenTarget:
    word: str
    context: dict | None
    reading: str
    config: dict
    cache_key: str


def controlled_target(db, settings, card_id: str, ref: DictionaryReference) -> TokenTarget:
    """Require one whole token at the exact UTF-16 position in the current publication."""
    _, version = published_card(db, card_id, ref.version_id)
    lines = [line for line in version.payload["dialogue"] if line["id"] == ref.line_id]
    valid = False
    if len(lines) == 1:
        text = lines[0]["english"]
        for match in TOKENS.finditer(text):
            if (match.start() and ASCII_NEIGHBOR.fullmatch(text[match.start() - 1])) or (
                match.end() < len(text) and ASCII_NEIGHBOR.fullmatch(text[match.end()])
            ):
                continue
            start = len(text[: match.start()].encode("utf-16-le")) // 2
            end = len(text[: match.end()].encode("utf-16-le")) // 2
            if ref.start == start and ref.end == end and ref.word == match.group():
                valid = True
                break
    if not valid:
        raise DomainError(422, "dictionary_reference_invalid", "请选择当前正文中完整的英文单词")
    matches = []
    for word in version.payload.get("vocabulary", []):
        source = word.get("source") or {}
        if (
            source.get("line_id") == ref.line_id
            and source.get("start") == ref.start
            and source.get("end") == ref.end
            and source.get("quote") == ref.word
        ):
            matches.append(word)
    context = matches[0] if len(matches) == 1 else None
    reading = ref.word
    if context and context["english"].strip().casefold() == ref.word.casefold():
        reading = (context.get("pronunciation_text") or ref.word).strip()
        if (
            context.get("pronunciation_issue")
            or not reading
            or len(reading) > 300
            or not reading.isprintable()
            or any(character in reading for character in "<>&")
        ):
            reading = ""
    config = configuration(settings)
    cache_key = fingerprint({"spelling": ref.word, "reading": reading, "configuration": config})
    return TokenTarget(ref.word, context, reading, config, cache_key)


def lookup(target: TokenTarget, gateway: DictionaryGateway) -> DictionaryResult:
    """Use exactly located confirmed context first, with optional explicit lexical metadata."""
    context = target.context
    meaning = (context.get("meaning") or "").strip() if context else ""
    lexical = None
    try:
        lexical = gateway.lookup(target.word)
    except DomainError:
        if not meaning:
            raise
    except Exception:
        if not meaning:
            raise DomainError(503, "dictionary_unavailable", "词典服务暂不可用，请重试") from None
    if meaning and context:
        same_spelling = context["english"].strip().casefold() == target.word.casefold()
        return DictionaryResult(
            word=target.word,
            lemma=lexical.lemma if lexical else None,
            phonetic=(context.get("phonetic") or "").strip()
            if same_spelling
            else (lexical.phonetic if lexical else ""),
            definitions=[Definition(meaning=meaning)],
            source="context",
            provider="context",
            speech_text=target.reading,
        )
    assert lexical is not None
    return DictionaryResult(
        **lexical.model_dump(),
        word=target.word,
        source="dictionary" if lexical.definitions else "missing",
        speech_text=target.reading,
    )
