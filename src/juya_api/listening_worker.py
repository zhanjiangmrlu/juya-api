"""Independent persistent listening queue; existing workers cannot consume these tasks.

Run: python -m juya_api.listening_worker [--once]
This bounded DB dispatcher also recovers processing leases after process restarts.
"""

import argparse
import logging
import signal
import time

from .config import Settings
from .database import make_database, utc_now
from .listening_timeline import pending_jobs, run_timeline_job


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    if settings.worker_role == "mini" or settings.image_role == "mini":
        parser.error("Listening timeline worker requires an admin or local role")
    engine, sessions = make_database(settings)
    running = True

    def stop(_signal, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        while running:
            try:
                for job_id in pending_jobs(sessions, utc_now()):
                    if not running:
                        break
                    run_timeline_job(settings, sessions, job_id)
            except Exception:
                logging.getLogger("juya.listening").warning("listening_queue_cycle_unavailable")
            if args.once:
                break
            time.sleep(5)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
