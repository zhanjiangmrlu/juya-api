"""Frozen feedback DTOs; whitespace and Unicode limits agree with the mini-program."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

FeedbackCategory = Literal["content", "pronunciation", "display", "function"]
FeedbackStatus = Literal["pending", "processing", "needs_info", "resolved"]
ImageID = Annotated[str, Field(min_length=1, max_length=36)]


class UserMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=500)
    images: list[ImageID] = Field(default_factory=list, max_length=3)

    @field_validator("text", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("images")
    @classmethod
    def unique_images(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("同一截图不能重复选择")
        return value


class CreateFeedback(UserMessage):
    category: FeedbackCategory
    source: Literal["profile", "scene"]
    card_id: str | None = Field(default=None, min_length=1, max_length=36)
    version_id: str | None = Field(default=None, min_length=1, max_length=36)

    @model_validator(mode="after")
    def source_reference(self):
        if self.source == "scene" and (not self.card_id or not self.version_id):
            raise ValueError("场景反馈必须包含当前卡片和发布版本")
        if self.source == "profile" and (self.card_id is not None or self.version_id is not None):
            raise ValueError("通用反馈不携带场景引用")
        return self


class AdminMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str | None = Field(default=None, min_length=1, max_length=500)
    status: Literal["processing", "needs_info", "resolved"] | None = None
    expected_latest_event_id: int | None = Field(default=None, ge=1)

    @field_validator("text", mode="before")
    @classmethod
    def trim_text(cls, value):
        return (value.strip() or None) if isinstance(value, str) else value

    @model_validator(mode="after")
    def explicit_action(self):
        if self.text is None and self.status is None:
            raise ValueError("请填写回复或选择处理动作")
        if self.status in {"needs_info", "resolved"} and self.text is None:
            raise ValueError("要求补充或标记已处理时请填写对应说明")
        return self


class ReadFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: int = Field(ge=1)


class FeedbackImage(BaseModel):
    id: str
    state: Literal["ready"]
    url: str
    content_type: str
    width: int
    height: int
    size: int


class FeedbackEvent(BaseModel):
    id: int
    actor: Literal["user", "admin"]
    text: str | None
    status: FeedbackStatus | None
    images: list[FeedbackImage]
    created_at: str


class FeedbackDetail(BaseModel):
    id: str
    user_id: str
    user_code: str
    category: FeedbackCategory
    status: FeedbackStatus
    summary: str
    source: Literal["profile", "scene"]
    card_id: str | None
    version_id: str | None
    source_title: str | None
    source_title_en: str
    source_available: bool
    source_unavailable_reason: Literal["offline", "deleted"] | None
    created_at: str
    updated_at: str
    unread: bool
    latest_event_id: int
    events: list[FeedbackEvent]


class FeedbackPage(BaseModel):
    items: list[FeedbackDetail]
    total: int
    page: int
    limit: int


class FeedbackUnread(BaseModel):
    unread: bool
    count: int


class FeedbackReadReceipt(BaseModel):
    feedback_id: str
    read_event_id: int
