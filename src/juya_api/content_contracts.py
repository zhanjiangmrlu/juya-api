"""Human-edited scene data, with safe text and explicit source fragments."""

from pydantic import BaseModel, Field, model_validator

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
    image_id: str | None = Field(default=None, max_length=36)
    audio_id: str | None = Field(default=None, max_length=36)
    dialogue: list[Dialogue] = Field(default_factory=list, max_length=200)
    vocabulary: list[Vocabulary] = Field(default_factory=list, max_length=100)
    chunks: list[Chunk] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def bounded_text(self):
        """Bound combined text memory for shared drafts and fifty-card import batches."""
        values = [self.name]
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


class CreateCard(BaseModel):
    content: SceneContent


class Revision(BaseModel):
    revision: int = Field(ge=1)


class SaveCard(Revision):
    content: SceneContent


class PublishCard(Revision):
    preview_id: str = Field(max_length=36)
