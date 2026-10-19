"""Own local development services and a reconnecting, restricted SSH reverse tunnel."""

import argparse
import fcntl
import hashlib
import ipaddress
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import urlsplit

IDENTITY = "juya-local-share"
DOMAINS = {
    "admin": "dev-admin.juyayingyu.com",
    "admin-api": "dev-admin-api.juyayingyu.com",
    "mini-api": "dev-api.juyayingyu.com",
}
PORTS = {"redis": 16379, "admin": 8001, "mini": 8002, "web": 4173}
FORWARDS = {34173: 4173, 38001: 8001, 38002: 8002}


def private_json(path, value):
    """Atomically save owner-only configuration or lifecycle state."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
    temporary.chmod(0o600)
    temporary.replace(path)


def read_state(path):
    """Reject foreign lifecycle records instead of adopting their PIDs."""
    if not path.exists():
        return {"controller": IDENTITY, "processes": {}}
    value = json.loads(path.read_text())
    if value.get("controller") != IDENTITY:
        raise RuntimeError("Unrecognized lifecycle state")
    return value


def process_info(pid, field):
    """Read process identity without trusting a stored PID alone."""
    result = subprocess.run(
        ["ps", "-p", str(int(pid)), "-o", field + "="], capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def owned_alive(record):
    """Require both the launch marker and process birth time to match."""
    pid = record.get("pid", 0)
    owner = record.get("owner", "")
    if not owner or not pid:
        return False
    command = process_info(pid, "args")
    return (
        str(Path(__file__).resolve()) in command
        and "--owner " + owner in command
        and process_info(pid, "lstart") == record.get("started")
    )


def stop_owned(record):
    """Stop only a verified process group created by this controller."""
    if not owned_alive(record):
        return False
    pid = record["pid"]
    try:
        if os.getpgid(pid) != pid:
            return False
        os.killpg(pid, signal.SIGTERM)
        for _ in range(50):
            if not owned_alive(record) or process_info(pid, "stat").startswith("Z"):
                return True
            time.sleep(0.1)
        if owned_alive(record):
            os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    return True


def require_free_port(port):
    """Fail before launch when a listener already owns a required port."""
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(f"Local port {port} is occupied; no process was stopped")


def share_settings(values, *, lan_address=None):
    """Retain local data and LAN access while adding the development web origin."""
    result = dict(values)
    if result.get("environment", "local") != "local":
        raise ValueError("Sharing requires the local environment")
    database = result.get("database_url", "")
    parsed = urlsplit(database)
    if not database.startswith("sqlite:///") and parsed.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise ValueError("Sharing requires a local database")
    result["environment"] = "local"
    origins = list(result.get("allowed_origins", []))
    origin = "https://" + DOMAINS["admin"]
    if origin not in origins:
        origins.append(origin)
    if lan_address and ipaddress.ip_address(lan_address).is_private:
        lan_origin = f"http://{lan_address}:4173"
        if lan_origin not in origins:
            origins.append(lan_origin)
    result["allowed_origins"] = origins
    return result


def probe(url, *, expected=(200,), marker=None):
    """Return a bounded, credential-free health result without following redirects."""
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            actual = response.headers.get("X-Juya-Local-Share")
            return {
                "ok": response.status in expected and (marker is None or actual == marker),
                "status": response.status,
                "local_share": bool(actual),
            }
    except urllib.error.HTTPError as error:
        actual = error.headers.get("X-Juya-Local-Share")
        return {
            "ok": error.code in expected and (marker is None or actual == marker),
            "status": error.code,
            "local_share": bool(actual),
        }
    except Exception:
        return {"ok": False, "status": "unreachable"}


def environment(config):
    """Remove inherited deployment overrides and load only the local configuration."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("JUYA_", "VITE_"))}
    for key, value in config["settings"].items():
        if value is None:
            continue
        env["JUYA_" + key.upper()] = (
            json.dumps(value) if isinstance(value, (list, dict, bool)) else str(value)
        )
    return env


def child_command(workspace, config, role):
    """Build a service command; credentials are supplied through environment or files."""
    backend = Path(__file__).resolve().parents[1]
    if role == "redis":
        return [config["redis_binary"], str(workspace / ".private/local-share/redis.conf")], backend
    if role == "worker":
        return [sys.executable, "-m", "juya_api.worker_main", "--pool", "solo"], backend
    if role == "dispatcher":
        return [sys.executable, "-m", "juya_api.dispatch"], backend
    if role == "web":
        return [
            str(workspace / ".tools/node/bin/pnpm"),
            "dev",
            "--mode",
            "local-share",
            "--host",
            "0.0.0.0",
            "--port",
            "4173",
            "--strictPort",
        ], Path(config["admin_dir"])
    if role == "tunnel":
        command = [
            "/usr/bin/ssh",
            "-C",
            "-nNT",
            "-i",
            str(workspace / ".private/local-share/id_ed25519"),
            "-o",
            "BatchMode=yes",
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "ExitOnForwardFailure=yes",
            "-o",
            "ServerAliveInterval=15",
            "-o",
            "ServerAliveCountMax=3",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "ControlMaster=no",
        ]
        for remote, local in FORWARDS.items():
            command += ["-R", f"127.0.0.1:{remote}:127.0.0.1:{local}"]
        command.append("juya-dev-tunnel@8.163.84.24")
        return command, backend
    raise ValueError("Unknown service role")


def serve(workspace, role, owner):
    """Run one owned service; only the SSH connection is automatically reconnected."""
    config = json.loads((workspace / ".private/local-share/config.json").read_text())
    env = environment(config)
    env["PATH"] = ":".join(
        [
            str(workspace / ".tools/node/bin"),
            str(workspace / ".tools/ffmpeg/bin"),
            env.get("PATH", ""),
        ]
    )
    if role == "web":
        env["VITE_API_BASE_URL"] = ""
        env["VITE_DEV_API_PROXY_TARGET"] = "http://127.0.0.1:8001"
    if role in {"admin", "mini"}:
        os.environ.clear()
        os.environ.update(env)
        import uvicorn

        from juya_api.admin import create_app as admin_app
        from juya_api.config import Settings
        from juya_api.mini import create_app as mini_app

        app = (admin_app if role == "admin" else mini_app)(Settings(**config["settings"]))

        @app.middleware("http")
        async def local_marker(request, call_next):
            response = await call_next(request)
            response.headers["X-Juya-Local-Share"] = config["instance_id"]
            return response

        uvicorn.run(app, host="127.0.0.1", port=PORTS[role], access_log=False)
        return
    command, cwd = child_command(workspace, config, role)
    running = True
    child = None

    def stop(_signal, _frame):
        nonlocal running
        running = False
        if child and child.poll() is None:
            child.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while running:
        child = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL)
        result = child.wait()
        if role == "tunnel" and running:
            ready_file = workspace / ".private/local-share" / ("tunnel-ready-" + owner)
            if not ready_file.exists():
                raise RuntimeError("SSH initial forwarding failed; no retries were started")
        if role != "tunnel" or not running:
            if result and running:
                raise RuntimeError("Service exited; inspect its private log")
            return
        print("SSH tunnel disconnected; retrying", flush=True)
        for _ in range(30):
            if not running:
                return
            time.sleep(0.1)


def redis_ready(config):
    """Check the authenticated local broker without exposing its URL."""
    try:
        import redis

        client = redis.Redis.from_url(config["settings"]["redis_url"], socket_timeout=2)
        try:
            return bool(client.ping())
        finally:
            client.close()
    except Exception:
        return False


def start(workspace, directory):
    """Start transactionally and preserve any already-owned healthy services."""
    config = json.loads((directory / "config.json").read_text())
    address = subprocess.run(
        ["/usr/sbin/ipconfig", "getifaddr", "en0"], capture_output=True, text=True
    ).stdout.strip()
    config["settings"] = share_settings(config["settings"], lan_address=address or None)
    config.setdefault("instance_id", uuid.uuid4().hex)
    fingerprint = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    state = read_state(directory / "state.json")
    for role, port in PORTS.items():
        if not owned_alive(state["processes"].get(role, {})):
            require_free_port(port)
    if state.get("config_digest") != fingerprint:
        for record in reversed(list(state["processes"].values())):
            stop_owned(record)
        state["processes"] = {}
    state["config_digest"] = fingerprint
    private_json(directory / "config.json", config)
    # Let SSH allocate every forwarding atomically; ExitOnForwardFailure rejects conflicts.
    owner = uuid.uuid4().hex
    launched = []
    try:
        for role in ["redis", "admin", "mini", "worker", "dispatcher", "web", "tunnel"]:
            if owned_alive(state["processes"].get(role, {})):
                continue
            log_path = directory / (role + ".log")
            fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, "a") as log:
                child = subprocess.Popen(
                    [
                        sys.executable,
                        str(Path(__file__).resolve()),
                        "--workspace",
                        str(workspace),
                        "serve",
                        role,
                        "--owner",
                        owner,
                    ],
                    cwd=Path(__file__).resolve().parents[1],
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            record = {
                "pid": child.pid,
                "owner": owner,
                "started": process_info(child.pid, "lstart"),
            }
            state["processes"][role] = record
            launched.append(role)
            private_json(directory / "state.json", state)
            for _ in range(120):
                if child.poll() is not None:
                    raise RuntimeError(f"{role} failed to start; inspect its private log")
                if role == "redis":
                    ready = redis_ready(config)
                elif role in {"admin", "mini"}:
                    result = probe(
                        f"http://127.0.0.1:{PORTS[role]}/health/ready", marker=config["instance_id"]
                    )
                    ready = result["ok"] and result.get("local_share")
                elif role == "web":
                    ready = probe("http://127.0.0.1:4173/")["ok"]
                elif role == "tunnel":
                    ready = probe(
                        "https://" + DOMAINS["admin"] + "/api/admin/v1/auth/session",
                        expected=(401,),
                        marker=config["instance_id"],
                    )["ok"]
                else:
                    time.sleep(1)
                    ready = child.poll() is None
                if ready:
                    if role == "tunnel":
                        (directory / ("tunnel-ready-" + owner)).touch(mode=0o600)
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError(f"{role} did not become ready")
        report = status(workspace, directory)
        if not report["running"]:
            raise RuntimeError("Not all local sharing routes are ready")
    except BaseException:
        for role in reversed(launched):
            stop_owned(state["processes"].pop(role))
        private_json(directory / "state.json", state)
        raise
    print(json.dumps(report, ensure_ascii=False, indent=2))


def status(workspace, directory):
    """Report process and route health without printing configuration or credentials."""
    state = read_state(directory / "state.json")
    processes = {name: owned_alive(record) for name, record in state["processes"].items()}
    result = {
        "running": bool(processes) and all(processes.values()),
        "processes": processes,
        "urls": {k: "https://" + v for k, v in DOMAINS.items()},
    }
    if processes:
        config = json.loads((directory / "config.json").read_text())
        result["local"] = {
            role: probe(f"http://127.0.0.1:{port}/health/ready", marker=config["instance_id"])
            for role, port in PORTS.items()
            if role in {"admin", "mini"}
        }
        result["https"] = {"admin-web": probe(result["urls"]["admin"] + "/")}
        for name, suffix in [
            ("admin", "/api/admin/v1/auth/session"),
            ("admin-api", "/api/admin/v1/auth/session"),
            ("mini-api", "/api/mini/v1/me"),
        ]:
            result["https"][name] = probe(
                result["urls"][name] + suffix, expected=(401,), marker=config["instance_id"]
            )
        result["redis"] = redis_ready(config)
        result["running"] = (
            result["running"]
            and result["redis"]
            and all(item["ok"] for item in [*result["local"].values(), *result["https"].values()])
        )
    return result


def main():
    """Serialize lifecycle changes and expose a small start/status/stop interface."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[3])
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ["start", "status", "stop"]:
        commands.add_parser(command)
    child = commands.add_parser("serve")
    child.add_argument("role", choices=[*PORTS, "worker", "dispatcher", "tunnel"])
    child.add_argument("--owner", required=True)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    directory = workspace / ".private/local-share"
    if args.command == "serve":
        serve(workspace, args.role, args.owner)
        return
    if args.command == "status":
        print(json.dumps(status(workspace, directory), ensure_ascii=False, indent=2))
        return
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory / "lifecycle.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.command == "start":
            start(workspace, directory)
        else:
            state = read_state(directory / "state.json")
            for record in reversed(list(state["processes"].values())):
                stop_owned(record)
            private_json(directory / "state.json", {"controller": IDENTITY, "processes": {}})
            print("Local sharing stopped; other services were not changed")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Runtime configuration can contain credentials; never print exception values.
        print(
            f"Local sharing failed ({type(error).__name__}); inspect private logs",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
