"""Explicit empty-schema bootstrap; never overwrite an existing administrator."""

import argparse
import sys

from juya_api.auth import create_administrator
from juya_api.config import Settings
from juya_api.database import make_database
from juya_api.schema import require_compatible_schema


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default="admin")
    args = parser.parse_args()
    try:
        password = sys.stdin.read(257).rstrip("\r\n")
        if not 12 <= len(password) <= 128:
            raise ValueError("administrator password length is invalid")
        settings = Settings()
        if settings.image_role != "admin" or settings.environment == "local":
            raise ValueError("bootstrap requires the selected nonlocal admin image")
        engine, sessions = make_database(settings)
        try:
            with sessions.begin() as db:
                require_compatible_schema(db, minimum_revision=16)
                create_administrator(db, args.username, password)
        finally:
            engine.dispose()
        print("Administrator initialized; no business content was seeded")
        return 0
    except Exception:
        print(
            "Administrator bootstrap failed; existing accounts were not overwritten",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
