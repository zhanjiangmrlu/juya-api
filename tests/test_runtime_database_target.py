"""Deployment accepts an explicitly selected RDS host while preserving target isolation."""

import importlib.util
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from juya_api.config import Settings

RDS_HOST = "production.mysql.rds.example.com"


@pytest.mark.parametrize("role", ["admin", "mini"])
@pytest.mark.parametrize(
    "host,expected_host,database,username,accepted",
    [
        ("mysql", None, "juya_production", "juya_production_app", True),
        (RDS_HOST, RDS_HOST, "juya_production", "juya_production_app", True),
        (RDS_HOST, None, "juya_production", "juya_production_app", False),
        ("mysql", RDS_HOST, "juya_production", "juya_production_app", False),
        ("other.example.com", RDS_HOST, "juya_production", "juya_production_app", False),
        (RDS_HOST, RDS_HOST, "juya_test", "juya_production_app", False),
        (RDS_HOST, RDS_HOST, "juya_production", "juya_test_app", False),
        (RDS_HOST, RDS_HOST, "juya_production", "juya_production_migration", False),
    ],
)
def test_production_preflight_requires_selected_database_target(
    monkeypatch, role, host, expected_host, database, username, accepted
):
    monkeypatch.delenv("JUYA_EXPECTED_DATABASE_HOST", raising=False)
    if expected_host is not None:
        monkeypatch.setenv("JUYA_EXPECTED_DATABASE_HOST", expected_host)
    settings = Settings(
        _env_file=None,
        environment="production",
        image_role=role,
        database_url=f"mysql+pymysql://{username}:fake@{host}/{database}",
        field_encryption_key=Fernet.generate_key().decode(),
        lookup_key="synthetic-lookup-key-at-least-32-characters",
        redis_url="redis://:fake@redis-production:6379/0",
        storage_backend="oss",
        oss_bucket="production-private",
        oss_region="cn-guangzhou",
        oss_endpoint="https://oss-cn-guangzhou.aliyuncs.com",
        oss_access_key_id="synthetic-id",
        oss_access_key_secret="synthetic-secret",
        wechat_app_id="synthetic-app",
        wechat_app_secret="synthetic-secret",
        tts_secret_id="synthetic-id",
        tts_secret_key="synthetic-secret",
    )
    path = Path(__file__).resolve().parents[1] / "deploy/runtime-preflight.py"
    spec = importlib.util.spec_from_file_location("runtime_database_target", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if accepted:
        module.check_target(settings, "production", role, "production-private")
    else:
        with pytest.raises(ValueError, match="database or broker target mismatch"):
            module.check_target(settings, "production", role, "production-private")
