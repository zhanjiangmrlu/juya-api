"""Lightweight host monitor: aggregate values only, debounced alarms, optional durable delivery."""

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit


def transition(state, observations):
    events = []
    for signal, bad in observations.items():
        if not re.fullmatch(r"[a-z0-9_.-]{1,100}", signal):
            raise ValueError("invalid monitor signal")
        previous = state.setdefault(signal, {"active": False, "bad": 0, "good": 0})
        if bad is None:
            previous.update(bad=0, good=0)
            continue
        previous["bad"] = min(2, previous["bad"] + 1) if bad else 0
        previous["good"] = min(2, previous["good"] + 1) if not bad else 0
        if not previous["active"] and previous["bad"] == 2:
            previous["active"] = True
            events.append({"signal": signal, "state": "firing"})
        elif previous["active"] and previous["good"] == 2:
            previous["active"] = False
            events.append({"signal": signal, "state": "recovered"})
    return events


def http_metrics(path, now):
    groups = {}
    try:
        with Path(path).open("rb") as source:
            size = source.seek(0, 2)
            source.seek(max(0, size - 4 * 1024 * 1024))
            if source.tell():
                source.readline()
            for line in source:
                try:
                    row = json.loads(line)
                    if not now - 300 <= float(row["time"]) <= now:
                        continue
                    if (
                        row["environment"] not in ("test", "production")
                        or row["service"] not in ("admin-api", "mini-api")
                        or row["kind"] not in ("business", "cloud", "media")
                    ):
                        continue
                    seconds, status = float(row["seconds"]), int(row["status"])
                    if not math.isfinite(seconds) or seconds < 0 or not 100 <= status <= 599:
                        continue
                    key = ".".join([row["environment"], row["service"], row["kind"]])
                    groups.setdefault(key, []).append((seconds, status >= 500))
                except (ValueError, KeyError, TypeError):
                    continue
    except OSError:
        return {}
    return {
        key: {
            "count": len(rows),
            "p95_seconds": sorted(x[0] for x in rows)[math.ceil(0.95 * len(rows)) - 1],
            "error_rate": sum(x[1] for x in rows) / len(rows),
        }
        for key, rows in groups.items()
    }


def save_state(path, state):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("monitor state cannot be a symlink")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, filename = tempfile.mkstemp(prefix=".juya-state-", dir=path.parent)
    temporary = Path(filename)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(state, stream)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def collect(environments=("test", "production")):
    now = time.time()
    http = http_metrics("/var/log/nginx/juya-rebuild-access.jsonl", now)
    memory = {
        line.split(":")[0]: int(line.split()[1])
        for line in Path("/proc/meminfo").read_text().splitlines()
        if line.startswith(("MemTotal:", "MemAvailable:"))
    }
    disk = shutil.disk_usage("/")
    metrics = {
        "memory_available_fraction": memory["MemAvailable"] / memory["MemTotal"],
        "disk_free_fraction": disk.free / disk.total,
        "load_per_cpu": os.getloadavg()[1] / max(1, os.cpu_count() or 1),
        "http": http,
        "environments": {},
    }
    signals = {
        "host.memory": metrics["memory_available_fraction"] < 0.1,
        "host.disk": metrics["disk_free_fraction"] < 0.15,
        "host.cpu": metrics["load_per_cpu"] > 1.5,
    }
    source = Path(__file__).with_name("metrics.py").read_text()
    for environment, base in [("test", 18000), ("production", 28000)]:
        if environment not in environments:
            continue
        prefix = "juya-rebuild-" + environment
        for role, port in [("admin", base + 1), ("mini", base + 2)]:
            name = prefix + "-" + role + "-" + role + "-api-1"
            key = environment + "." + role + "-api"
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health/ready", timeout=3
                ) as response:
                    value = json.loads(response.read(4096))
                    healthy = (
                        value.get("status") == "ready"
                        and value.get("service") == role
                        and value.get("environment") == environment
                    )
            except Exception:
                healthy = False
            signals[key + ".health"] = not healthy
            for suffix, field, limit in [
                ("latency", "p95_seconds", 0.5),
                ("errors", "error_rate", 0.01),
            ]:
                rows = http.get(key + ".business", {})
                signals[key + "." + suffix] = (
                    rows[field] > limit if rows.get("count", 0) >= 20 else None
                )
            for kind in ("api", "worker", "dispatcher"):
                container = prefix + "-" + role + "-" + role + "-" + kind + "-1"
                try:
                    result = subprocess.run(
                        ["docker", "inspect", container], capture_output=True, text=True, timeout=5
                    )
                    info = json.loads(result.stdout)[0]["State"]
                    signals[environment + "." + role + "." + kind + ".container"] = (
                        info.get("Status") != "running"
                        or info.get("Health", {}).get("Status") != "healthy"
                        or info.get("OOMKilled", False)
                    )
                except Exception:
                    signals[environment + "." + role + "." + kind + ".container"] = True
            if role == "admin":
                try:
                    result = subprocess.run(
                        ["docker", "exec", "-i", name, "python", "-"],
                        input=source,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    data = json.loads(result.stdout)
                except Exception:
                    data = {"available": False}
                metrics["environments"][environment] = data
                signals[environment + ".database"] = not data.get("available")
                for field, limit in [
                    ("connections", 70),
                    ("oldest_pending_seconds", 300),
                    ("expired_leases", 0),
                ]:
                    signals[environment + "." + field] = (
                        data[field] > limit if data.get("available") else None
                    )
                signals[environment + ".tts_failures"] = (
                    data["tts_failed"] / data["tts_completed"] > 0.1
                    if data.get("tts_completed", 0) >= 10
                    else None
                )
    return metrics, signals


def deliver(outbox, webhook_file):
    path = Path(webhook_file)
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError("notification configuration must be private")
    url = path.read_text().strip()
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "open.feishu.cn"
        or not parsed.path.startswith("/open-apis/bot/v2/hook/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("invalid notification destination")
    while outbox:
        event = outbox[0]
        payload = json.dumps(
            {
                "msg_type": "text",
                "content": {"text": "句芽监控 " + event["state"] + ": " + event["signal"]},
            }
        ).encode()
        request = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            result = json.loads(response.read(4096))
            if response.status != 200 or result.get("code") != 0:
                raise ValueError("notification failed")
        outbox.pop(0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--state", type=Path, default=Path("/var/lib/juya-rebuild-monitor/state.json")
    )
    parser.add_argument("--notify", action="store_true")
    parser.add_argument("--environment", action="append", choices=["test", "production"])
    parser.add_argument("--webhook-file", type=Path)
    args = parser.parse_args()
    state = (
        json.loads(args.state.read_text()) if args.state.exists() else {"signals": {}, "outbox": []}
    )
    metrics, observations = collect(args.environment or ("test", "production"))
    events = transition(state["signals"], observations)
    if args.notify:
        if not args.webhook_file:
            raise ValueError("explicit notification file required")
        if not state.get("notifying"):
            initial = [
                {"signal": key, "state": "firing"}
                for key, value in state["signals"].items()
                if value["active"]
            ]
            events = [event for event in events if event["state"] != "firing"] + initial
        state["outbox"].extend(events)
    state["notifying"] = args.notify
    save_state(args.state, state)
    notification_failed = False
    if args.notify:
        try:
            deliver(state["outbox"], args.webhook_file)
        except Exception:
            notification_failed = True
        save_state(args.state, state)
    print(
        json.dumps(
            {
                "metrics": metrics,
                "events": events,
                "active": [key for key, value in state["signals"].items() if value["active"]],
                "notifications_enabled": args.notify,
                "notification_failed": notification_failed,
            }
        )
    )


if __name__ == "__main__":
    main()
