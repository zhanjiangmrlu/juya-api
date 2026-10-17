"""Explicit Worker process entry point; importing domain code never starts a broker client."""

import argparse

from .config import Settings
from .worker import celery_app


def main():
    """Use a single bounded worker; solo is available for isolated local process verification."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", choices=["prefork", "solo"], default="prefork")
    arguments = parser.parse_args()
    settings = Settings()
    if settings.environment != "local" and not settings.worker_role:
        parser.error("a Worker role is required outside local verification")
    app = celery_app(settings)
    app.worker_main(
        [
            "worker",
            "--loglevel=WARNING",
            "--concurrency=1",
            "--pool=" + arguments.pool,
            "--max-tasks-per-child=20",
            "--without-gossip",
            "--without-mingle",
        ]
    )


if __name__ == "__main__":
    main()
