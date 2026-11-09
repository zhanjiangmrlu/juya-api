"""Human-edited scene data, with safe text and explicit source fragments."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import identifier


class Dialogue(BaseModel):
    id: str = Field(default_factory=identifier, max_length=64)
    speaker: str = Field(default="", max_length=80)
    english: str = Field(default="", max_length=20000)
    chinese: str = Field(default="", max_length=20000)


class Source(BaseModel):
    line_id: str = Field(max_length=64)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(max_length=2000)


class Vocabulary(BaseModel):
    id: str = Field(default_factory=identifier, max_length=64)
    english: str = Field(default="", max_length=300)
    meaning: str = Field(default="", max_length=2000)
    phonetic: str = Field(default="", max_length=300)
    source: Source | None = None
    pronunciation_text: str = Field(default="", max_length=300)
    pronunciation_issue: bool = False


class Chunk(BaseModel):
    id: str = Field(default_factory=identifier, max_length=64)
    english: str = Field(default="", max_length=2000)
    chinese: str = Field(default="", max_length=2000)


class SceneContent(BaseModel):
    name: str = Field(default="", max_length=160)
    title_en: str = Field(default="", max_length=300)
    image_id: str | None = Field(default=None, max_length=36)
    audio_id: str | None = Field(default=None, max_length=36)
    dialogue: list[Dialogue] = Field(default_factory=list, max_length=200)
    vocabulary: list[Vocabulary] = Field(default_factory=list, max_length=100)
    chunks: list[Chunk] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def bounded_text(self):
        """Bound combined text memory for shared drafts and fifty-card import batches."""
        values = [self.name, self.title_en]
        for line in self.dialogue:
            values.extend([line.speaker, line.english, line.chinese])
        for word in self.vocabulary:
            values.extend([word.english, word.meaning, word.phonetic, word.pronunciation_text])
        for chunk in self.chunks:
            values.extend([chunk.english, chunk.chinese])
        # Derived IDs/highlight references do not make a normalized saved card invalid.
        if sum(len(value.encode("utf-8")) for value in values) > 512 * 1024:
            raise ValueError("资料文字过多，请拆分为多张卡片")
        return self


class StudyNoteChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["keep", "set", "remove", "unresolved"]
    media_id: str | None = Field(default=None, min_length=1, max_length=36)
    previous_media_id: str | None = Field(default=None, min_length=1, max_length=36)

    @model_validator(mode="after")
    def selection_matches_action(self):
        """Only an explicit set operation may carry one selected PDF."""
        if "previous_media_id" in self.model_fields_set and (
            self.action not in {"set", "unresolved"} or self.previous_media_id is None
        ):
            raise ValueError("仅设置或待选择笔记可提供明确的有效保留PDF标识")
        if (self.action == "set") != (self.media_id is not None):
            raise ValueError("设置笔记须提供PDF，其他操作不提供媒体标识")
        return self


class CreateCard(BaseModel):
    content: SceneContent
    study_note: StudyNoteChange | None = None


class Revision(BaseModel):
    revision: int = Field(ge=1)


class SaveCard(Revision):
    content: SceneContent
    study_note: StudyNoteChange | None = None


class PublishCard(Revision):
    preview_id: str = Field(max_length=36)
