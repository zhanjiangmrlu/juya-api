"""Public response whitelists used by runtime serialization and generated clients."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from .content_contracts import SceneContent


class PublicModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Page[T](PublicModel):
    items: list[T]
    total: int
    page: int
    limit: int


class AdministratorIdentity(PublicModel):
    id: str
    username: str


class AdminLoginResponse(PublicModel):
    administrator: AdministratorIdentity
    csrf_token: str


class AdminSessionResponse(AdministratorIdentity):
    csrf_token: str


class UserProfile(PublicModel):
    id: str
    nickname: str
    avatar_id: str | None
    phone: str | None
    wechat_contact: str | None
    phone_source: str | None
    wechat_source: str | None
    profile_version: int
    contact_version: int
    registered_at: str
    last_login_at: str


class WechatLoginResponse(PublicModel):
    access_token: str
    expires_at: str
    user: UserProfile


class LogoutResponse(PublicModel):
    logged_out: bool


class FieldIssue(PublicModel):
    field: str
    code: str
    message: str


class CardView(PublicModel):
    id: str
    display_name: str
    display_thumbnail_id: str | None
    status: str
    current_version_id: str | None
    draft_revision: int
    content: SceneContent
    sort_order: int
    updated_at: str
    has_unpublished_changes: bool
    issues: list[FieldIssue]


class CardPreview(PublicModel):
    preview_id: str
    revision: int
    content: SceneContent
    expires_at: str
    mode: Literal["draft"]


class CardState(PublicModel):
    completed: bool
    today_completed: bool
    favorite: bool


class CardBrief(PublicModel):
    id: str
    name: str
    version_id: str
    thumbnail_id: str | None
    published_at: str
    state: CardState


class PublishedDetail(PublicModel):
    card_id: str
    version_id: str
    content: SceneContent
    published_at: str
    state: CardState


class PublishedPreview(PublicModel):
    card_id: str
    version_id: str
    content: SceneContent
    mode: Literal["published"]


class DeletedCard(PublicModel):
    id: str
    deleted: bool


class MediaMetadata(PublicModel):
    id: str
    kind: str
    state: str
    content_type: str
    size: int
    width: int | None
    height: int | None
    duration: float | None
    thumbnail_id: str | None
    original_name: str | None = None
    job_id: str | None = None
    error: str | None = None


class ResourceURL(PublicModel):
    url: str
    expires_at: str


class Statistics(PublicModel):
    date: str
    completed_cards: int
    current_streak: int
    longest_streak: int
    total_checkin_days: int
    checked_in_today: bool
    today_completed_cards: int
    last_studied_at: str | None
    favorite_count: int


class CompletionResponse(PublicModel):
    card_id: str
    version_id: str
    date: str
    first_completion: bool
    first_checkin_today: bool
    state: CardState
    statistics: Statistics


class FavoriteResponse(PublicModel):
    card_id: str
    favorite: bool


class CardSummary(PublicModel):
    id: str
    name: str
    thumbnail_id: str | None
    available: bool
    version_id: str | None
    unavailable_reason: str | None


class PersonalSummary(CardSummary):
    state: CardState


class LearningRecord(CardSummary):
    first_completed_at: str
    last_completed_at: str


class DailyRecord(CardSummary):
    completed_at: str


class CheckinRecord(PublicModel):
    date: str
    card_count: int


class DailyRecords(PublicModel):
    date: str
    total: int
    items: list[DailyRecord]


class AdminUser(UserProfile):
    statistics: Statistics


class AdminUserPage(Page[AdminUser]):
    statistical_date: str


class Overview(PublicModel):
    user_count: int
    new_users_today: int
    published_card_count: int
    statistical_date: str
    updated_at: str


class AvatarUpload(PublicModel):
    id: str
    state: str
    job_id: str | None = None


class AvatarURL(PublicModel):
    url: str | None


class OperationResponse(PublicModel):
    status: Literal["succeeded"]
    result: dict[str, Any]


class ErrorBody(PublicModel):
    code: str
    message: str
    details: list[dict[str, Any]] | None = None


class ErrorResponse(PublicModel):
    error: ErrorBody
    request_id: str | None = None


class UploadConfiguration(PublicModel):
    image_limit_bytes: int
    audio_limit_bytes: int
    archive_limit_bytes: int
    import_card_limit: int


class ClientConfiguration(PublicModel):
    avatar_limit_bytes: int
