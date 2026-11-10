"""Bounded, retryable retirement of legacy contact fields and encrypted receipts.

Only database rows listed here are touched. Callers must stop legacy writers and
confirm the environment/database before invoking an applied run.
"""

import json
from collections.abc import Callable
from typing import Any, cast

from sqlalchemy import Table, and_, delete, or_, select, tuple_, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from .config import Settings
from .content_models import Operation
from .models import Consent, LoginOperation, User
from .security import decrypt, encrypt

CONTACT_COLUMNS = (
    "phone_cipher",
    "phone_digest",
    "phone_source",
    "wechat_cipher",
    "wechat_digest",
    "wechat_source",
    "contact_updated_at",
)
CONTACT_RECEIPT_KEYS = (
    "phone",
    "wechat_contact",
    "phone_source",
    "wechat_source",
    "contact_version",
)
COUNT_NAMES = (
    "users_cleared",
    "contact_operations_deleted",
    "contact_consents_deleted",
    "profile_receipts_cleaned",
    "login_receipts_cleaned",
)


class _ReceiptError(Exception):
    """A receipt could not be safely inspected; never include its data in errors."""


def _clean_receipt(settings: Settings, value: str, *, login: bool) -> str | None:
    try:
        payload = json.loads(decrypt(settings, value) or "")
        if not isinstance(payload, dict):
            raise _ReceiptError
        user = payload.get("user") if login else payload
        if login and user is None:
            return None
        if not isinstance(user, dict):
            raise _ReceiptError
        if not any(key in user for key in CONTACT_RECEIPT_KEYS):
            return None
        for key in CONTACT_RECEIPT_KEYS:
            user.pop(key, None)
        return encrypt(settings, json.dumps(payload, ensure_ascii=False))
    except Exception:
        # Fernet/JSON/encoding exceptions may contain supplied values. A private
        # marker lets the batch runner report counts without retaining details.
        raise _ReceiptError from None


def clean_contact_data(
    sessions: sessionmaker[Session],
    settings: Settings,
    *,
    apply: bool = False,
    batch_size: int = 100,
) -> dict[str, int | str]:
    """Inspect by default; apply commits one bounded batch at a time.

    Counts describe committed changes (or proposed changes for a dry run).
    Any failed batch is rolled back in full and omitted from change counts;
    processing stops and the overall status remains ``incomplete``.
    Rerunning scans all candidates, including expired login receipts.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    counts: dict[str, int] = dict.fromkeys(COUNT_NAMES, 0)
    counts.update(scanned_rows=0, successful_batches=0, failed_batches=0, receipt_failures=0)

    def run(
        table: Table,
        condition: ColumnElement[bool],
        count_name: str,
        mutate: Callable[[Session, RowMapping, ColumnElement[bool]], bool],
    ) -> bool:
        columns = list(table.primary_key.columns)
        after: tuple[Any, ...] | None = None
        while True:
            rows: list[RowMapping] = []
            try:
                with sessions() as db:
                    if not apply and db.get_bind().dialect.name == "sqlite":
                        db.connection(execution_options={"sqlite_write_intent": False})
                    query = select(table).where(condition).order_by(*columns).limit(batch_size)
                    if after is not None:
                        query = query.where(tuple_(*columns) > tuple_(*after))
                    rows = list(db.execute(query).mappings())
                    if not rows:
                        return True
                    after = tuple(rows[-1][column.name] for column in columns)
                    counts["scanned_rows"] += len(rows)
                    changed = 0
                    for row in rows:
                        identity = and_(*(column == row[column.name] for column in columns))
                        changed += int(mutate(db, row, identity))
                    if apply:
                        db.commit()
                    else:
                        db.rollback()
                    counts[count_name] += changed
                    counts["successful_batches"] += 1
            except Exception as error:
                # Session close rolls back both DML and commit failures. Do not
                # log exception text, SQL parameters, row identifiers or values.
                counts["failed_batches"] += 1
                if isinstance(error, _ReceiptError):
                    counts["receipt_failures"] += 1
                return False

    users = cast(Table, User.__table__)
    operations = cast(Table, Operation.__table__)
    consents = cast(Table, Consent.__table__)
    logins = cast(Table, LoginOperation.__table__)

    def clear_user(db: Session, row: RowMapping, identity: ColumnElement[bool]) -> bool:
        if apply:
            db.execute(update(users).where(identity).values(dict.fromkeys(CONTACT_COLUMNS)))
        return True

    def remove(table: Table) -> Callable[[Session, RowMapping, ColumnElement[bool]], bool]:
        def execute(db: Session, row: RowMapping, identity: ColumnElement[bool]) -> bool:
            if apply:
                db.execute(delete(table).where(identity))
            return True

        return execute

    def receipt(
        table: Table,
        column_name: str,
        *,
        login: bool,
    ) -> Callable[[Session, RowMapping, ColumnElement[bool]], bool]:
        def execute(db: Session, row: RowMapping, identity: ColumnElement[bool]) -> bool:
            value = _clean_receipt(settings, row[column_name], login=login)
            if value is None:
                return False
            if apply:
                db.execute(update(table).where(identity).values({column_name: value}))
            return True

        return execute

    stages = (
        (
            users,
            or_(*(users.c[name].is_not(None) for name in CONTACT_COLUMNS)),
            "users_cleared",
            clear_user,
        ),
        (
            operations,
            operations.c.action == "contact.save",
            "contact_operations_deleted",
            remove(operations),
        ),
        (
            consents,
            consents.c.purpose.in_(("contact.phone", "contact.wechat")),
            "contact_consents_deleted",
            remove(consents),
        ),
        (
            operations,
            operations.c.action == "profile.save",
            "profile_receipts_cleaned",
            receipt(operations, "result", login=False),
        ),
        (
            logins,
            and_(logins.c.result_cipher.is_not(None), logins.c.result_cipher != ""),
            "login_receipts_cleaned",
            receipt(logins, "result_cipher", login=True),
        ),
    )
    for table, condition, count_name, mutate in stages:
        if not run(table, condition, count_name, mutate):
            break
    status = "incomplete" if counts["failed_batches"] else "complete" if apply else "dry_run"
    return {"status": status, **counts}
