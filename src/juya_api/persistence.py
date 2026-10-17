"""Atomic identity/idempotency reservations without duplicate-insert lock upgrades."""

from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert


def insert_once(db, model, values: dict, unique_fields: list[str]):
    """Reserve a unique row while leaving the winner's original values unchanged."""
    if db.get_bind().dialect.name == "mysql":
        mysql_statement = mysql_insert(model).values(**values)
        # Updating a matching unique field to itself acquires an exclusive record
        # lock directly. Never replace a winning user's primary identifier.
        field = unique_fields[0]
        db.execute(
            mysql_statement.on_duplicate_key_update(**{field: mysql_statement.inserted[field]})
        )
    else:
        sqlite_statement = (
            sqlite_insert(model)
            .values(**values)
            .on_conflict_do_nothing(index_elements=unique_fields)
        )
        db.execute(sqlite_statement)
