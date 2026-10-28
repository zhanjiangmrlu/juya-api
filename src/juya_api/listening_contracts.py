"""Public typed listening contracts shared by both isolated API entrypoints."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from .response_contracts import DailyRecord, LearningPermission, Statistics


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Expression(Input):
    english: str = Field(default="", max_length=1000)
    chinese: str = Field(default="", max_length=2000)
    example: str = Field(default="", max_length=3000)


class WordMeaning(Input):
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    word: str = Field(min_length=1, max_length=300)
    lemma: str | None = Field(default=None, max_length=300)
    phonetic: str = Field(default="", max_length=300)
    chinese: str = Field(min_length=1, max_length=3000)


class ListeningPayload(Input):
    title_zh: str = Field(default="", max_length=160)
    title_en: str = Field(default="", max_length=300)
    tags: list[str] = Field(default_factory=list, max_length=30)
    body_en: str = Field(default="", max_length=100000)
    translation_zh: str = Field(default="", max_length=100000)
    expressions: list[Expression] = Field(default_factory=list, max_length=20)
    word_meanings: list[WordMeaning] = Field(default_factory=list, max_length=1000)
    audio_id: str | None = Field(default=None, max_length=36)
    image_id: str | None = Field(default=None, max_length=36)


class CategoryInput(Input):
    name: str = Field(min_length=1, max_length=160)
    name_en: str | None = Field(default=None, max_length=300)
    sort_order: StrictInt = 0


class CategoryUpdate(CategoryInput):
    revision: int = Field(ge=1)


class Category(CategoryUpdate):
    id: str
    name_en: str = ""


class TopicInput(Input):
    name: str = Field(min_length=1, max_length=160)
    sort_order: StrictInt = 0
    category_id: str = Field(min_length=1, max_length=36)
    description: str | None = Field(default=None, max_length=2000)


class TopicUpdate(TopicInput):
    revision: int = Field(ge=1)


class Topic(TopicUpdate):
    id: str
    description: str = ""


class TopicProgress(Topic):
    total_articles: int
    completed_articles: int


class ArticleInput(Input):
    topic_id: str = Field(min_length=1, max_length=36)
    payload: ListeningPayload


class ArticleUpdate(ArticleInput):
    revision: int = Field(ge=1)


class Revision(Input):
    revision: int = Field(ge=1)


class TimelineWord(Input):
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    sentence_id: str = Field(min_length=1, max_length=64)


class Timeline(BaseModel):
    state: Literal["pending", "processing", "ready", "needs_attention", "failed", "missing"]
    input_hash: str | None = None
    job_id: str | None = None
    words: list[TimelineWord] = Field(default_factory=list)
    reviewed_at: str | None = None
    error_code: str | None = None


class TimelineInput(Revision):
    input_hash: str
    words: list[TimelineWord] = Field(max_length=20000)


class Article(BaseModel):
    id: str
    topic_id: str
    status: str
    revision: int
    version_id: str | None
    topic_order: int
    global_order: int
    payload: ListeningPayload
    word_count: int
    timeline: Timeline
    created_at: str
    deleted_at: str | None
    batch_id: str | None = None
    draft_topic_id: str | None = None
    draft_topic_order: int | None = None
    published_topic_id: str | None = None
    published_topic_order: int | None = None


class ArticleState(BaseModel):
    favorite: bool
    completed: bool
    today_completed: bool


class Summary(BaseModel):
    id: str
    content_type: Literal["listening"] = "listening"
    topic_id: str
    title_zh: str
    title_en: str
    tags: list[str]
    word_count: int
    version_id: str | None
    available: bool
    thumbnail_url: str | None
    access: LearningPermission
    state: ArticleState
    first_completed_at: str | None = None
    last_completed_at: str | None = None
    favorited_at: str | None = None
    completed_at: str | None = None


class VersionInput(Input):
    version_id: str = Field(min_length=1, max_length=36)


class ProgressInput(VersionInput):
    reading_position: int = Field(
        ge=0,
        description=(
            "原始body_en的Unicode code point字符位置，非滚动像素；JS使用Array.from(body_en)计数"
        ),
    )
    translation_open: bool
    audio_position: float = Field(ge=0, allow_inf_nan=False)
    playback_rate: float = Field(json_schema_extra={"enum": [1, 1.25, 1.5, 1.75, 2]})

    @field_validator("playback_rate")
    @classmethod
    def supported_rate(cls, value):
        if value not in {1, 1.25, 1.5, 1.75, 2}:
            raise ValueError("请选择支持的五档倍速")
        return value


class Progress(ProgressInput):
    updated_at: str | None = None


class ArticleDetail(Summary):
    payload: ListeningPayload
    progress: Progress
    timeline: Timeline
    queue_token: str
    audio_duration: float


class Home(BaseModel):
    categories: list[Category]
    topics: list[TopicProgress]
    continue_learning: Summary | None
    configured: bool
    authorization: dict
    free_count: int | None
    actual_free_count: int
    scene_free_count: int | None
    scene_actual_free_count: int
    statistics: Statistics


class NextArticle(BaseModel):
    article: Summary | None
    ended: bool


class PublishInput(Revision):
    preview_token: str


class ArticlePreview(BaseModel):
    article: Article
    preview_token: str
    errors: list[str]


class OrderInput(Input):
    scope: Literal["global", "topic"]
    topic_id: str | None = None
    article_ids: list[str] = Field(max_length=50000)
    revision: int = Field(ge=0)


class OrderResult(BaseModel):
    revision: int
    article_ids: list[str]


class FreeCount(Input):
    free_count: StrictInt = Field(ge=0, le=2147483647)


class Confirmation(Input):
    preview_token: str


class FreePolicy(BaseModel):
    configured: bool
    free_count: int | None
    revision: int
    article_ids: list[str]


class FreePreview(BaseModel):
    preview_token: str
    free_count: int
    article_ids: list[str]
    added_ids: list[str]
    removed_ids: list[str]
    revision: int


class DeleteItem(Revision):
    id: str


class BatchDelete(Input):
    items: list[DeleteItem] = Field(min_length=1, max_length=50)


class DeleteResult(BaseModel):
    id: str
    status: Literal["success", "failed"]
    error: str | None = None


class BatchDeleteResult(BaseModel):
    items: list[DeleteResult]


class FavoriteResult(BaseModel):
    article_id: str
    favorite: bool


class ListeningCompletionResult(BaseModel):
    article_id: str
    version_id: str
    date: str
    first_completion: bool
    first_checkin_today: bool
    state: ArticleState
    statistics: Statistics


class ListeningDictionaryReference(VersionInput):
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("请选择完整英文词项")
        return self


class MediaTicketInput(VersionInput):
    media_id: str


class TicketResult(BaseModel):
    url: str
    expires_at: str


class ListeningCheckin(BaseModel):
    date: str
    card_count: int
    article_count: int


class ListeningDailyRecord(Summary):
    completed_at: str


class MixedDay(BaseModel):
    date: str
    scene_items: list[DailyRecord]
    article_items: list[ListeningDailyRecord]
    card_count: int
    article_count: int
