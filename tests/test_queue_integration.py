"""Real Redis transport and a separate Celery process; no fake queue/task execution."""

import base64
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("JUYA_TEST_REDIS_URL"), reason="Isolated real Redis required"
)


def test_committed_upload_survives_missing_dispatch_and_duplicate_broker_delivery(
    system, admin, tmp_path
):
    from redis import Redis

    from juya_api.jobs import dispatch
    from juya_api.worker import celery_app

    from .content_helpers import key, picture

    system["time"][0] = datetime.now(UTC)
    settings = system["settings"]
    settings.redis_url = os.environ["JUYA_TEST_REDIS_URL"]
    accepted = admin.post(
        "/api/admin/v1/media?kind=image",
        headers=key(),
        files={"file": ("actual-worker.png", picture(), "image/png")},
    )
    assert accepted.status_code == 201
    medium = accepted.json()
    assert medium["state"] == "processing"
    celery = celery_app(settings)
    now = system["admin"].app.state.clock()
    assert (
        dispatch(
            system["sessions"], now, lambda job_id: celery.send_task("juya.execute", args=[job_id])
        )
        == 1
    )
    # The broker envelope contains only a task identity, not media bytes or credentials.
    redis = Redis.from_url(settings.redis_url)
    messages = redis.lrange("celery", 0, -1)
    assert messages
    message = json.loads(messages[-1])
    envelope = json.loads(base64.b64decode(message["body"]))
    assert envelope[0] == [medium["job_id"]]
    assert settings.field_encryption_key not in json.dumps(message)
    celery.send_task("juya.execute", args=[medium["job_id"]])
    env = dict(os.environ)
    for name, value in settings.model_dump(mode="json").items():
        env["JUYA_" + name.upper()] = (
            json.dumps(value)
            if isinstance(value, (list, dict))
            else str(value).lower()
            if isinstance(value, bool)
            else str(value)
        )
    log = tmp_path / "worker.log"
    with log.open("w") as output:
        process = subprocess.Popen(
            [sys.executable, "-m", "juya_api.worker_main", "--pool", "solo"],
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    pytest.fail("Worker exited; inspect the private verification log")
                status = admin.get(f"/api/admin/v1/media/{medium['id']}/status").json()
                if status["state"] == "ready":
                    break
                time.sleep(0.2)
            else:
                pytest.fail("Real Worker did not finish the accepted media")
            assert status["width"] == 120 and status["height"] == 80
            from juya_api.job_models import Job

            with system["sessions"]() as db:
                assert db.get(Job, medium["job_id"]).attempts == 1
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    assert settings.field_encryption_key not in log.read_text()
    if settings.redis_url in log.read_text():
        pytest.fail("Worker exposed a broker connection credential")
