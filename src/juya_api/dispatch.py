"""Recover durable task deliveries without coupling API availability to Redis."""

import logging
import signal
import time

from .config import Settings
from .database import make_database, utc_now
from .jobs import dispatch
from .worker import celery_app


def main():
    """Keep scanning after broker/database outages; do not log credential-bearing exceptions."""
    settings = Settings()
    if settings.environment != "local" and not settings.worker_role:
        raise RuntimeError("A dispatcher role is required outside local verification")
    engine, sessions = make_database(settings)
    celery = celery_app(settings)
    running = True

    def stop(_signal, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        while running:
            try:
                dispatch(
                    sessions,
                    utc_now(),
                    lambda job_id: celery.send_task("juya.execute", args=[job_id]),
                    role=settings.worker_role,
                )
            except Exception:
                logging.getLogger("juya.jobs").warning("dispatcher_cycle_unavailable")
            time.sleep(5)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
