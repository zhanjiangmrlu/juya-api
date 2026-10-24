"""Fail closed on environment, role and dependency mismatches without printing secrets."""

import os
import sys
from urllib.parse import urlsplit

from redis import Redis
from sqlalchemy import text
from sqlalchemy.engine import make_url

from juya_api.config import Settings
from juya_api.database import make_database
from juya_api.schema import require_compatible_schema


def check_target(settings, environment, role, expected_bucket):
    if environment not in ("test", "production") or role not in ("admin", "mini"):
        raise ValueError("explicit environment and role required")
    if settings.environment != environment or settings.image_role != role:
        raise ValueError("image/runtime target mismatch")
    database = make_url(settings.database_url)
    redis = urlsplit(settings.redis_url)
    prefix = "juya_test" if environment == "test" else "juya_production"
    if (
        database.drivername != "mysql+pymysql"
        or database.database != prefix
        or database.username != prefix + "_app"
        or database.host != settings.expected_database_host
        or not database.password
        or redis.hostname != "redis-" + environment
        or not redis.password
        or redis.path != "/0"
    ):
        raise ValueError("database or broker target mismatch")
    if (
        settings.storage_backend != "oss"
        or not expected_bucket
        or settings.oss_bucket != expected_bucket
        or not settings.oss_region
        or not settings.oss_endpoint.startswith("https://")
        or not settings.oss_access_key_id
        or not settings.oss_access_key_secret
        or not settings.cookie_secure
        or not settings.wechat_app_id
        or not settings.wechat_app_secret
        or not settings.tts_secret_id
        or not settings.tts_secret_key
    ):
        raise ValueError("private cloud runtime configuration incomplete")


def main():
    try:
        if len(sys.argv) not in (3, 4) or (
            len(sys.argv) == 4 and sys.argv[3] != "--before-migration"
        ):
            raise ValueError("invalid preflight arguments")
        settings = Settings()
        check_target(settings, sys.argv[1], sys.argv[2], os.getenv("JUYA_EXPECTED_OSS_BUCKET"))
        engine, sessions = make_database(settings)
        try:
            with sessions.begin() as db:
                db.execute(text("SELECT 1"))
                if len(sys.argv) == 3:
                    require_compatible_schema(
                        db, minimum_revision=17 if settings.image_role == "admin" else 10
                    )
        finally:
            engine.dispose()
        redis = Redis.from_url(settings.redis_url, socket_timeout=5, socket_connect_timeout=5)
        try:
            if not redis.ping():
                raise ValueError("broker unavailable")
        finally:
            redis.close()
        print("runtime preflight passed")
        return 0
    except Exception:
        print("runtime preflight failed; check the selected role and environment", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
