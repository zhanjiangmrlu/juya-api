"""Anonymous current-publication summaries and revocable display-only image copies."""

from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .content_models import Media
from .content_service import published_card
from .dependencies import database
from .errors import DomainError
from .share_contracts import PublicSceneShare
from .share_images import SHARE_DIMENSIONS, unavailable
from .storage import ObjectStorage


def share_titles(version):
    """Historical missing English stays empty without changing existing official titles."""
    name, title_en = version.payload.get("name"), version.payload.get("title_en")
    if title_en is None:
        title_en = ""
    if not isinstance(name, str) or not name.strip() or not isinstance(title_en, str):
        raise DomainError(503, "publication_unavailable", "场景资料暂不可用")
    return name, title_en if title_en.strip() else ""


def share_source(db, card_id, version_id=None):
    card, version = published_card(db, card_id, version_id)
    share_titles(version)
    image_id = version.payload.get("image_id")
    medium = db.get(Media, image_id) if isinstance(image_id, str) else None
    if (
        not medium
        or medium.kind != "image"
        or medium.owner_kind != "admin"
        or medium.state != "ready"
    ):
        raise unavailable()
    return card, version, medium


def recheck(db, card, version):
    """A publication changed during storage IO cannot escape through an old identity-map row."""
    db.expire(card)
    published_card(db, card.id, version.id)


def routes():
    router = APIRouter(prefix="/api/mini/v1/public/cards", tags=["public share summaries"])

    @router.get("/{card_id}/share", response_model=PublicSceneShare)
    def summary(card_id: str, request: Request, db: Session = Depends(database, scope="function")):
        card, version, medium = share_source(db, card_id)
        request.app.state.share_images.prepare(
            card.id, version.id, medium, ObjectStorage(request.app.state.settings), SHARE_DIMENSIONS
        )
        recheck(db, card, version)
        name, title_en = share_titles(version)
        prefix = (
            f"/api/mini/v1/public/cards/{quote(card.id, safe='')}/share/images/"
            f"{quote(version.id, safe='')}/"
        )
        return {
            "card_id": card.id,
            "version_id": version.id,
            "name": name,
            "title_en": title_en,
            "images": {
                variant: {"url": prefix + variant, "width": size[0], "height": size[1]}
                for variant, size in SHARE_DIMENSIONS.items()
            },
        }

    @router.head("/{card_id}/share/images/{version_id}/{variant}", include_in_schema=False)
    @router.get(
        "/{card_id}/share/images/{version_id}/{variant}",
        response_class=Response,
        responses={200: {"content": {"image/jpeg": {}}}},
    )
    def image(
        card_id: str,
        version_id: str,
        variant: Literal["friends", "timeline"],
        request: Request,
        db: Session = Depends(database, scope="function"),
    ):
        card, version, medium = share_source(db, card_id, version_id)
        data = request.app.state.share_images.prepare(
            card.id, version.id, medium, ObjectStorage(request.app.state.settings), [variant]
        )[variant]
        recheck(db, card, version)
        return Response(
            content=b"" if request.method == "HEAD" else data,
            media_type="image/jpeg",
            headers={
                "Content-Length": str(len(data)),
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router
