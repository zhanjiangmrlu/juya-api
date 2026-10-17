"""Alarm debounce and telemetry aggregation never carry request paths or user data."""

import importlib.util
import json
from pathlib import Path


def script():
    path = Path(__file__).resolve().parents[1] / "deploy/monitor.py"
    spec = importlib.util.spec_from_file_location("monitor", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_alerts_require_two_samples_deduplicate_and_do_not_recover_from_missing_data():
    module = script()
    state = {}
    assert module.transition(state, {"production.admin-api.health": True}) == []
    assert module.transition(state, {"production.admin-api.health": True}) == [
        {"signal": "production.admin-api.health", "state": "firing"}
    ]
    assert module.transition(state, {"production.admin-api.health": True}) == []
    assert module.transition(state, {"production.admin-api.health": None}) == []
    assert state["production.admin-api.health"]["active"]
    assert module.transition(state, {"production.admin-api.health": False}) == []
    assert module.transition(state, {"production.admin-api.health": False}) == [
        {"signal": "production.admin-api.health", "state": "recovered"}
    ]
    assert not state["production.admin-api.health"]["active"]


def test_http_metrics_separate_business_cloud_and_media_and_ignore_sensitive_fields(tmp_path):
    module = script()
    path = tmp_path / "access.jsonl"
    records = [
        {
            "time": 1000,
            "environment": "test",
            "service": "mini-api",
            "kind": "business",
            "seconds": 0.1,
            "status": 200,
            "path": "/secret-grant?token=never-output",
        }
        for _ in range(20)
    ]
    records += [
        {
            "time": 1000,
            "environment": "test",
            "service": "mini-api",
            "kind": "media",
            "seconds": 40,
            "status": 500,
        },
        {
            "time": 1000,
            "environment": "test",
            "service": "mini-api",
            "kind": "cloud",
            "seconds": 30,
            "status": 200,
        },
        {
            "time": 500,
            "environment": "test",
            "service": "mini-api",
            "kind": "business",
            "seconds": 80,
            "status": 500,
        },
    ]
    path.write_text("\n".join(json.dumps(x) for x in records))
    value = module.http_metrics(path, now=1001)
    assert value["test.mini-api.business"] == {"count": 20, "p95_seconds": 0.1, "error_rate": 0}
    assert value["test.mini-api.media"]["p95_seconds"] == 40
    assert "never-output" not in json.dumps(value)


def test_sql_metrics_count_pending_expired_and_recent_speech_without_payloads(system):
    from datetime import timedelta

    from juya_api.jobs import enqueue

    path = Path(__file__).resolve().parents[1] / "deploy/metrics.py"
    spec = importlib.util.spec_from_file_location("metrics", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    now = system["time"][0].replace(tzinfo=None)
    with system["sessions"].begin() as db:
        enqueue(
            db,
            "media.decode",
            "admin",
            "actor",
            {"private": "never-output"},
            now - timedelta(seconds=400),
            settings=system["settings"],
        )
        running = enqueue(
            db, "media.decode", "admin", "actor", {}, now, settings=system["settings"]
        )
        running.state = "running"
        running.lease_expires_at = now - timedelta(seconds=1)
        for index in range(10):
            speech = enqueue(
                db, "tts.synthesize", "mini", "actor", {}, now, settings=system["settings"]
            )
            speech.state = "failed" if index == 0 else "succeeded"
    with system["sessions"]() as db:
        value = module.snapshot(db, now, connections=7)
    assert value == {
        "available": True,
        "connections": 7,
        "pending_jobs": 1,
        "oldest_pending_seconds": 400,
        "expired_leases": 1,
        "tts_completed": 10,
        "tts_failed": 1,
    }
    assert "never-output" not in json.dumps(value)


def test_test_only_collection_never_probes_deferred_production(monkeypatch):
    import io
    from types import SimpleNamespace

    module = script()
    original_read = Path.read_text
    requested = []

    def read_text(path, *args, **kwargs):
        if str(path) == "/proc/meminfo":
            return "MemTotal: 8000000 kB\nMemAvailable: 6000000 kB\n"
        return original_read(path, *args, **kwargs)

    def urlopen(url, **kwargs):
        requested.append(url)
        role = "admin" if ":18001/" in url else "mini"
        return io.BytesIO(
            json.dumps({"status": "ready", "service": role, "environment": "test"}).encode()
        )

    def run(args, **kwargs):
        requested.extend(args)
        if args[1] == "inspect":
            return SimpleNamespace(
                stdout=json.dumps(
                    [{"State": {"Status": "running", "Health": {"Status": "healthy"}}}]
                )
            )
        return SimpleNamespace(
            stdout=json.dumps(
                {
                    "available": True,
                    "connections": 2,
                    "oldest_pending_seconds": 0,
                    "expired_leases": 0,
                }
            )
        )

    monkeypatch.setattr(Path, "read_text", read_text)
    monkeypatch.setattr(module, "http_metrics", lambda *args: {})
    monkeypatch.setattr(module.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(module.subprocess, "run", run)
    metrics, signals = module.collect(("test",))
    assert set(metrics["environments"]) == {"test"}
    assert not any(key.startswith("production.") for key in signals)
    assert not any("production" in item or ":2800" in item for item in requested)
