"""A historical reference authorizes its thumbnail, never its old full publication."""

from .content_models import Card, CardVersion, Media
from .errors import DomainError
from .learning_models import Completion, Favorite


def summary_thumbnail(db, user_id: str, card_id: str, media_id: str, version_id=None):
    """Require a real owned history/favorite link and the last-publication thumbnail."""
    owned = db.get(Completion, (user_id, card_id)) or db.get(Favorite, (user_id, card_id))
    card = db.get(Card, card_id)
    if not owned or not card or not card.current_version_id:
        raise DomainError(404, "media_missing", "未找到本人记录中的缩略图")
    if version_id and version_id != card.current_version_id:
        raise DomainError(409, "version_changed", "摘要已更新，请刷新")
    version = db.get(CardVersion, card.current_version_id)
    image = db.get(Media, version.payload["image_id"]) if version else None
    if not image or image.thumbnail_id != media_id:
        raise DomainError(404, "media_missing", "历史记录仅保留安全缩略图")
    return version
