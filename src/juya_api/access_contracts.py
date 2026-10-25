"""Shared, generated-client-visible access DTOs."""

from typing import Any, Literal

from pydantic import BaseModel


class AuthorizationView(BaseModel):
    status: Literal["none", "active", "expired"]
    starts_on: str | None
    expires_on: str | None
    expires_at: str | None
    revision: int


class PolicyView(BaseModel):
    enabled: bool
    free_count: int | None
    revision: int
    actual_free_count: int = 0


class CurrentAccess(BaseModel):
    enabled: bool
    free_count: int | None
    revision: int
    authorization: AuthorizationView
    server_now: str


class FreeScene(BaseModel):
    id: str
    name: str
    title_en: str
    thumbnail_id: str | None
    change: str | None = None


class FreePolicyPreview(PolicyView):
    proposed_count: int
    total: int
    page: int
    limit: int
    items: list[FreeScene]
    added_count: int
    removed_count: int
    removed: list[FreeScene]
    preview_token: str


class AuthorizationTarget(BaseModel):
    starts_on: str
    expires_on: str | None
    status: str


class GrantPreview(BaseModel):
    user_id: str
    before: AuthorizationView
    after: AuthorizationTarget
    preview_token: str


class AccessEvent(BaseModel):
    id: str
    action: str
    admin_id: str
    before: dict[str, Any]
    after: dict[str, Any]
    occurred_at: str


class AccessHistoryPage(BaseModel):
    items: list[AccessEvent]
    total: int
    page: int
    limit: int
