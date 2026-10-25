"""本人来源队列的固定顺序快照和实时资格校验"""

from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .access_service import access_context, free_uncompleted, learning_access, require_access
from .content_models import Card
from .content_service import published_card
from .dependencies import database, learner, operation_key
from .discovery_models import LearningQueue, LearningQueueItem
from .errors import DomainError
from .learning_models import Completion, DailyLearning, Favorite
from .learning_service import card_state
from .response_contracts import CardState
from .transactions import operate

QueueSource = Literal["learning", "favorites", "records", "day"]


class CreateLearningQueue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: QueueSource
    card_id: str = Field(min_length=1, max_length=36)
    day: date | None = None

    @model_validator(mode="after")
    def require_source_day(self):
        """仅日期来源必须且允许携带所选打卡日期"""
        if (self.source == "day") != (self.day is not None):
            raise ValueError("日期队列必须提供来源日期，其他队列不传日期")
        return self


class QueueCreated(BaseModel):
    id: str
    source: QueueSource
    total: int


class QueueItemView(BaseModel):
    card_id: str
    state: CardState
    available: bool


class QueuePage(BaseModel):
    end_reason: Literal["round_complete", "free_complete"] = "round_complete"
    items: list[QueueItemView]
    total: int
    offset: int
    next_offset: int | None


def source_ids(db, user_id, body):
    """按来源列表原有排序读取ID，参数为本人及已校验来源条件"""
    if body.source == "learning":
        completed = select(Completion.card_id).where(Completion.user_id == user_id)
        # 当前卡可能刚在其他设备完成，保留它以便重查状态后继续后续队列
        query = (
            select(Card.id)
            .where(
                Card.status == "published",
                Card.deleted_at.is_(None),
                or_(Card.id.not_in(completed), Card.id == body.card_id),
            )
            .order_by(Card.sort_order, Card.id)
        )
    elif body.source == "favorites":
        query = (
            select(Favorite.card_id)
            .where(Favorite.user_id == user_id)
            .order_by(Favorite.created_at.desc(), Favorite.card_id)
        )
    elif body.source == "records":
        query = (
            select(Completion.card_id)
            .join(Card, Completion.card_id == Card.id)
            .where(Completion.user_id == user_id, Card.deleted_at.is_(None))
            .order_by(Completion.last_completed_at.desc(), Completion.card_id)
        )
    else:
        query = (
            select(DailyLearning.card_id)
            .join(Card, DailyLearning.card_id == Card.id)
            .where(
                DailyLearning.user_id == user_id,
                DailyLearning.date == body.day,
                Card.deleted_at.is_(None),
            )
            .order_by(DailyLearning.accepted_at.desc(), DailyLearning.card_id)
        )
    ids = list(db.scalars(query))
    if body.card_id not in ids:
        raise DomainError(409, "queue_source_changed", "来源列表已变化，请返回列表重新进入")
    return ids[ids.index(body.card_id) :]


def queue_eligible(db, queue, card_id, state):
    """根据快照来源和当前本人关系判断该项是否仍可推进"""
    card = db.get(Card, card_id)
    if not card or card.deleted_at or card.status != "published" or not card.current_version_id:
        return False
    if not learning_access(db, queue.user_id, card_id, db.info["now"])["can_learn"]:
        return False
    if queue.source == "learning":
        return not state["completed"]
    if queue.source == "favorites":
        return state["favorite"]
    if queue.source == "records":
        return state["completed"]
    return db.get(DailyLearning, (queue.user_id, card_id, queue.day)) is not None


def routes():
    """注册用户独有的本次队列创建及分页读取接口"""
    router = APIRouter(prefix="/api/mini/v1/learning-queues", tags=["source learning queues"])

    @router.post("", response_model=QueueCreated, status_code=201)
    def create(
        body: CreateLearningQueue,
        request: Request,
        user=Depends(learner),
        key: str = Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        """为当前用户的来源条件建立可幂等恢复的固定顺序快照"""
        now = request.app.state.clock()

        def execute():
            """在同一事务写入队列及从点击卡向后的所有稳定ID"""
            require_access(db, user.id, body.card_id, request.app.state.clock(), lock=True)
            published_card(db, body.card_id)
            ids = source_ids(db, user.id, body)
            queue = LearningQueue(
                user_id=user.id,
                source=body.source,
                day=body.day,
                created_at=now,
                expires_at=now + timedelta(hours=24),
            )
            db.add(queue)
            db.flush()
            db.add_all(
                [
                    LearningQueueItem(queue_id=queue.id, position=index, card_id=card_id)
                    for index, card_id in enumerate(ids)
                ]
            )
            db.flush()
            return {"id": queue.id, "source": queue.source, "total": len(ids)}

        return operate(
            db,
            user,
            "mini",
            key,
            "learning.queue.create",
            body.model_dump(mode="json"),
            now,
            execute,
        )

    @router.get("/{queue_id}", response_model=QueuePage)
    def read(
        queue_id: str,
        request: Request,
        offset: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=50),
        user=Depends(learner),
        db: Session = Depends(database, scope="function"),
    ):
        """读取本人快照索引，失效项保留位置，不能让分页移位"""
        queue = db.get(LearningQueue, queue_id)
        if not queue or queue.user_id != user.id:
            raise DomainError(404, "queue_missing", "未找到本次学习列表，请返回列表重新进入")
        now = request.app.state.clock()
        if queue.expires_at <= now:
            raise DomainError(410, "queue_expired", "本次学习列表已过期，请返回列表重新进入")
        total = (
            db.scalar(
                select(func.count())
                .select_from(LearningQueueItem)
                .where(LearningQueueItem.queue_id == queue.id)
            )
            or 0
        )
        rows = db.scalars(
            select(LearningQueueItem)
            .where(LearningQueueItem.queue_id == queue.id)
            .order_by(LearningQueueItem.position)
            .offset(offset)
            .limit(limit)
        ).all()
        items = []
        for row in rows:
            state = card_state(db, user.id, row.card_id, now)
            items.append(
                {
                    "card_id": row.card_id,
                    "state": state,
                    "available": queue_eligible(db, queue, row.card_id, state),
                }
            )
        context = access_context(db, user.id, now)
        free_complete = (
            context["enabled"]
            and context["authorization"]["status"] != "active"
            and free_uncompleted(db, user.id) == 0
            and bool(
                db.scalar(
                    select(Card.id)
                    .where(
                        Card.status == "published",
                        Card.deleted_at.is_(None),
                        Card.id.not_in(
                            select(Completion.card_id).where(Completion.user_id == user.id)
                        ),
                    )
                    .limit(1)
                )
            )
        )
        return {
            "end_reason": "free_complete" if free_complete else "round_complete",
            "items": items,
            "total": total,
            "offset": offset,
            "next_offset": offset + len(rows) if offset + len(rows) < total else None,
        }

    return router
