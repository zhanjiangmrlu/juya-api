"""The local sharing controller must never adopt or stop unrelated processes."""

import importlib.util
import json
import os
import signal
import socket
import subprocess
import sys
from pathlib import Path

import pytest

SOURCE = Path(__file__).parents[1] / "deploy/local_share.py"


def controller():
    assert SOURCE.exists(), "local sharing controller has not been implemented"
    spec = importlib.util.spec_from_file_location("local_share", SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_stop_does_not_signal_an_unrelated_live_process(tmp_path):
    tool = controller()
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        record = {"pid": child.pid, "owner": "not-this-process", "started": "incorrect"}
        assert tool.stop_owned(record) is False
        assert child.poll() is None
    finally:
        child.terminate()
        child.wait()


def test_occupied_port_is_rejected_without_contacting_or_stopping_its_owner():
    tool = controller()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        with pytest.raises(RuntimeError, match="occupied"):
            tool.require_free_port(listener.getsockname()[1])
        assert listener.fileno() >= 0


def test_configuration_requires_local_database_and_preserves_lan_origins(tmp_path):
    tool = controller()
    settings = {
        "environment": "local",
        "database_url": f"sqlite:///{tmp_path}/ui.sqlite",
        "media_root": str(tmp_path / "media"),
        "allowed_origins": ["http://192.168.1.2:4173"],
        "wechat_app_id": "wxexample",
        "wechat_app_secret": "private",
    }
    result = tool.share_settings(settings)
    assert result["allowed_origins"] == [
        "http://192.168.1.2:4173",
        "https://dev-admin.juyayingyu.com",
    ]
    assert settings["allowed_origins"] == ["http://192.168.1.2:4173"]
    with pytest.raises(ValueError, match="local"):
        tool.share_settings({**settings, "environment": "production"})
    with pytest.raises(ValueError, match="local"):
        tool.share_settings({**settings, "database_url": "mysql://cloud-server/database"})


def test_stop_does_not_delete_a_foreign_state_file(tmp_path):
    tool = controller()
    state = {"controller": "another-tool", "processes": {}}
    target = tmp_path / "state.json"
    target.write_text(json.dumps(state))
    with pytest.raises(RuntimeError, match="state"):
        tool.read_state(target)
    assert json.loads(target.read_text()) == state


def test_cli_status_handles_unstarted_environment_without_secrets(tmp_path):
    controller()
    result = subprocess.run(
        [sys.executable, str(SOURCE), "--workspace", str(tmp_path), "status"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report["running"] is False
    assert "processes" in report


def test_private_state_files_are_owner_only(tmp_path):
    tool = controller()
    target = tmp_path / "state.json"
    tool.private_json(target, {"controller": "juya-local-share", "processes": {}})
    assert os.stat(target).st_mode & 0o777 == 0o600


def test_optional_settings_do_not_become_invalid_none_environment_strings(monkeypatch):
    tool = controller()
    monkeypatch.setenv("JUYA_WORKER_ROLE", "mini")
    result = tool.environment({"settings": {"worker_role": None, "environment": "local"}})
    assert result.get("JUYA_WORKER_ROLE") is None
    assert result["JUYA_ENVIRONMENT"] == "local"


def test_current_lan_address_is_added_without_dropping_previous_origins():
    tool = controller()
    result = tool.share_settings(
        {"database_url": "sqlite:////tmp/local.sqlite", "allowed_origins": []},
        lan_address="192.168.0.100",
    )
    assert "http://192.168.0.100:4173" in result["allowed_origins"]


def test_first_ssh_failure_exits_instead_of_retrying_forever(tmp_path, monkeypatch):
    tool = controller()
    directory = tmp_path / ".private/local-share"
    tool.private_json(directory / "config.json", {"settings": {}})
    monkeypatch.setattr(
        tool,
        "child_command",
        lambda *_: ([sys.executable, "-c", "raise SystemExit(1)"], tmp_path),
    )
    before = {sig: signal.getsignal(sig) for sig in [signal.SIGTERM, signal.SIGINT]}
    try:
        with pytest.raises(RuntimeError, match="initial"):
            tool.serve(tmp_path, "tunnel", "test-owner")
    finally:
        for sig, handler in before.items():
            signal.signal(sig, handler)


def test_status_rejects_a_disconnected_h5_api_even_when_other_routes_are_ready(
    tmp_path, monkeypatch
):
    tool = controller()
    directory = tmp_path / ".private/local-share"
    tool.private_json(
        directory / "config.json", {"instance_id": "this-local-instance", "settings": {}}
    )
    tool.private_json(
        directory / "state.json",
        {
            "controller": tool.IDENTITY,
            "processes": {
                role: {}
                for role in [
                    "redis",
                    "admin",
                    "mini",
                    "worker",
                    "dispatcher",
                    "web",
                    "h5",
                    "tunnel",
                ]
            },
        },
    )
    monkeypatch.setattr(tool, "owned_alive", lambda _: True)
    monkeypatch.setattr(tool, "redis_ready", lambda _: True)
    calls = []

    def probe(url, **options):
        calls.append((url, options))
        return {"ok": url != "https://dev-h5.juyayingyu.com/api/mini/v1/me"}

    monkeypatch.setattr(tool, "probe", probe)
    result = tool.status(tmp_path, directory)
    assert result["running"] is False
    assert (
        "https://dev-h5.juyayingyu.com/api/mini/v1/me",
        {"expected": (401,), "marker": "this-local-instance"},
    ) in calls


def test_status_requires_an_owned_h5_process_even_if_public_routes_answer(tmp_path, monkeypatch):
    tool = controller()
    directory = tmp_path / ".private/local-share"
    tool.private_json(directory / "config.json", {"instance_id": "this-instance", "settings": {}})
    tool.private_json(
        directory / "state.json",
        {
            "controller": tool.IDENTITY,
            "processes": {
                role: {}
                for role in ["redis", "admin", "mini", "worker", "dispatcher", "web", "tunnel"]
            },
        },
    )
    monkeypatch.setattr(tool, "owned_alive", lambda _: True)
    monkeypatch.setattr(tool, "redis_ready", lambda _: True)
    monkeypatch.setattr(tool, "probe", lambda *_args, **_kwargs: {"ok": True})
    assert tool.status(tmp_path, directory)["running"] is False


def test_start_retires_old_tunnel_when_the_forwarding_spec_is_upgraded(tmp_path, monkeypatch):
    import hashlib
    from types import SimpleNamespace

    tool = controller()
    directory = tmp_path / ".private/local-share"
    config = {
        "instance_id": "this-instance",
        "settings": tool.share_settings(
            {
                "database_url": "sqlite:////tmp/local-share.sqlite",
            }
        ),
    }
    tool.private_json(directory / "config.json", config)
    old_state = {
        "controller": tool.IDENTITY,
        "config_digest": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
        "processes": {
            role: {"role": role} for role in [*tool.PORTS, "worker", "dispatcher", "tunnel"]
        },
    }
    tool.private_json(directory / "state.json", old_state)
    stopped = []
    monkeypatch.setattr(tool, "owned_alive", bool)
    monkeypatch.setattr(tool, "stop_owned", lambda record: stopped.append(record["role"]))
    monkeypatch.setattr(
        tool.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(stdout="")
    )
    monkeypatch.setattr(tool, "status", lambda *_args: {"running": True})

    def intercepted_launch(*_args, **_kwargs):
        raise RuntimeError("controlled launch boundary")

    monkeypatch.setattr(tool.subprocess, "Popen", intercepted_launch)
    with pytest.raises(RuntimeError, match="controlled launch boundary"):
        tool.start(tmp_path, directory)
    assert "tunnel" in stopped
