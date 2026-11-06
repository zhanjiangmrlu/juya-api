"""Container probes print no exception, connection URL, credential or request path."""

import json
import os
import sys
import urllib.request


def main():
    try:
        if sys.argv[1:] == ["api"]:
            with urllib.request.urlopen(
                "http://127.0.0.1:8000/health/ready", timeout=5
            ) as response:
                value = json.loads(response.read(4096))
                assert response.status == 200 and value["status"] == "ready"
                assert value["service"] == os.environ["JUYA_IMAGE_ROLE"]
        elif sys.argv[1:] == ["worker"]:
            from redis import Redis

            from juya_api.config import Settings
            from juya_api.database import make_database
            from juya_api.schema import require_compatible_schema

            settings = Settings()
            assert settings.worker_role == settings.image_role
            redis = Redis.from_url(settings.redis_url, socket_timeout=3, socket_connect_timeout=3)
            try:
                assert redis.ping()
            finally:
                redis.close()
            engine, sessions = make_database(settings)
            try:
                with sessions() as db:
                    require_compatible_schema(db)
            finally:
                engine.dispose()
        else:
            return 1
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
