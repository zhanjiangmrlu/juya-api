#!/usr/bin/env python3
"""Inspect legacy contact data; --apply is the only write switch."""

import argparse
import json
from pathlib import Path

from sqlalchemy.engine import make_url

from juya_api.config import Settings
from juya_api.contact_cleanup import clean_contact_data
from juya_api.database import make_database


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="Private environment file")
    parser.add_argument("--environment", choices=("local", "test", "production"), required=True)
    parser.add_argument("--database-host", required=True, help="Expected host; SQLite: local-file")
    parser.add_argument("--database-port", type=int, default=3306, help="Expected MySQL port")
    parser.add_argument(
        "--database-name", required=True, help="Expected database; SQLite: file path"
    )
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        if not args.config.is_file() or args.batch_size < 1:
            raise ValueError
        settings = Settings(_env_file=args.config)
        url = make_url(settings.database_url)
        host = "local-file" if url.get_backend_name() == "sqlite" else url.host
        if (
            settings.environment != args.environment
            or host != args.database_host
            or url.database != args.database_name
            or (url.get_backend_name() != "sqlite" and (url.port or 3306) != args.database_port)
        ):
            raise ValueError
        engine, sessions = make_database(settings)
    except Exception:
        print(json.dumps({"status": "configuration_error"}))
        return 2
    try:
        counts = clean_contact_data(
            sessions, settings, apply=args.apply, batch_size=args.batch_size
        )
        print(json.dumps(counts, sort_keys=True))
        return 1 if counts["status"] == "incomplete" else 0
    except Exception:
        # Never emit settings, URL, SQL/parameters, decoded payloads or traceback.
        print(json.dumps({"status": "failed"}))
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
