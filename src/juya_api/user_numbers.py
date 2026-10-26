"""Persistent human-facing numbers with transactional registration allocation."""

import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .content_models import SettingCounter
from .models import User
from .persistence import insert_once


def user_code(number: int) -> str:
    """Format a persisted user number without truncating numbers above three digits."""
    return f"Juya{number:03d}"


def searched_user_number(value: str) -> int:
    """Parse a full visible code while rejecting values outside the database integer range."""
    match = re.fullmatch(r"juya([0-9]+)", value.strip(), re.I)
    number = int(match[1]) if match else 0
    return number if 0 < number <= 2_147_483_647 else -1


def registered_user(db: Session, app_id: str, identity: str, now: datetime) -> User:
    """Lock existing identities or serialize new identity numbering in the same transaction."""
    query = select(User).where(User.app_id == app_id, User.openid_digest == identity)
    user = db.scalar(query.with_for_update())
    if user is not None:
        return user
    insert_once(db, SettingCounter, {"name": "user_number", "value": 0}, ["name"])
    counter = db.scalar(
        select(SettingCounter).where(SettingCounter.name == "user_number").with_for_update()
    )
    assert counter is not None
    # A concurrent code for this identity may have registered it while we waited.
    user = db.scalar(query.with_for_update().execution_options(populate_existing=True))
    if user is not None:
        return user
    counter.value += 1
    user = User(
        app_id=app_id,
        openid_digest=identity,
        user_number=counter.value,
        registered_at=now,
        last_login_at=now,
    )
    db.add(user)
    db.flush()
    return user
