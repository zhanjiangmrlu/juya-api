"""只在同一发布版本恢复用户明确保存的正文锚点"""

from fastapi import APIRouter, Depends, Request
from pydantic import ConfigDict
from sqlalchemy.orm import Session

from .access_service import require_access
from .content_service import published_card
from .dependencies import database, learner, operation_key
from .discovery_models import ReadingStart
from .errors import DomainError
from .persistence import insert_once
from .response_contracts import ReadingPosition
from .transactions import operate


class SaveReadingPosition(ReadingPosition):
    model_config = ConfigDict(extra="forbid")


def routes():
    """注册本人版本绑定阅读位置接口，不更改任何成绩"""
    router = APIRouter(prefix="/api/mini/v1", tags=["trusted reading position"])

    @router.put("/cards/{card_id}/reading-position", response_model=ReadingPosition)
    def save(
        card_id: str,
        body: SaveReadingPosition,
        request: Request,
        user=Depends(learner),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        """保存当前用户在卡片同版正文中的锚点和块内相对进度"""
        now = request.app.state.clock()

        def execute():
            """在有效版本校验后写入本人锚点，重放请求不重复覆盖新位置"""
            require_access(db, user.id, card_id, request.app.state.clock(), lock=True)
            _, version = published_card(db, card_id, body.version_id)
            if body.anchor != "top":
                group, _, item_id = body.anchor.partition(":")
                collection = {
                    "dialogue": "dialogue",
                    "vocabulary": "vocabulary",
                    "chunk": "chunks",
                }.get(group)
                if not collection or not any(
                    row["id"] == item_id for row in version.payload.get(collection, [])
                ):
                    raise DomainError(422, "reading_anchor_invalid", "阅读位置已变化，请从顶部继续")
            insert_once(
                db,
                ReadingStart,
                {"user_id": user.id, "card_id": card_id, "started_at": now},
                ["user_id", "card_id"],
            )
            record = db.get(ReadingStart, (user.id, card_id))
            assert record is not None
            record.position = body.model_dump()
            db.flush()
            return record.position

        return operate(
            db,
            user,
            "mini",
            key,
            f"cards.{card_id}.reading-position",
            body.model_dump(),
            now,
            execute,
        )

    return router
