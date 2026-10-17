"""Fresh infrastructure credentials are isolated, durable and never silently rotated."""

import importlib.util
import json
import stat
from pathlib import Path

import pytest


def script():
    path = Path(__file__).resolve().parents[1] / "deploy/initialize-infrastructure.py"
    spec = importlib.util.spec_from_file_location("initialize_infrastructure", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_infrastructure_setup_resumes_without_rotating_keys_or_cross_environment_access(tmp_path):
    module = script()
    mysql, redis = "sha256:" + "a" * 64, "sha256:" + "b" * 64
    result = module.prepare(tmp_path / "rebuild", mysql, redis)
    again = module.prepare(tmp_path / "rebuild", mysql, redis)
    assert result == again
    values = result["environments"]
    for key in [
        "app_password",
        "migration_password",
        "redis_password",
        "field_encryption_key",
        "lookup_key",
    ]:
        assert values["test"][key] != values["production"][key]
    sql = module.account_sql(result)
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON `juya_test`.*" in sql
    assert "GRANT ALL PRIVILEGES ON `juya_production`.*" in sql
    assert "DROP " not in sql and "ALTER USER" not in sql
    assert stat.S_IMODE((tmp_path / "rebuild/infrastructure-secrets.json").stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "rebuild/secrets").stat().st_mode) == 0o700
    assert (
        "maxmemory-policy noeviction" in (tmp_path / "rebuild/secrets/redis-test.conf").read_text()
    )
    with pytest.raises(ValueError):
        module.prepare(tmp_path / "rebuild", "sha256:" + "c" * 64, redis)
    # A malformed state must never trigger generation of replacement credentials.
    state = tmp_path / "rebuild/infrastructure-secrets.json"
    state.write_text(json.dumps({"environments": {}}))
    with pytest.raises(ValueError):
        module.prepare(tmp_path / "rebuild", mysql, redis)
