"""Explicit anonymous share whitelists, independent of private learning DTOs."""

from pydantic import Field

from .response_contracts import PublicModel


class PublicShareImage(PublicModel):
    url: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class PublicShareImages(PublicModel):
    friends: PublicShareImage
    timeline: PublicShareImage


class PublicSceneShare(PublicModel):
    card_id: str
    version_id: str
    name: str
    title_en: str = ""
    images: PublicShareImages
