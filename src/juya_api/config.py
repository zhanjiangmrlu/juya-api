"""Typed runtime configuration; application secrets never have fallback values."""

from pathlib import Path
from typing import Literal

from cryptography.fernet import Fernet
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JUYA_", env_file=".env", extra="ignore")

    environment: Literal["local", "test", "production"] = "local"
    database_url: str
    field_encryption_key: str
    lookup_key: str
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    allowed_origins: list[str] = []
    cookie_secure: bool = True
    session_days: int = 7
    admin_session_hours: int = 12
    media_root: Path = Path("var/media")
    storage_backend: Literal["local", "oss"] = "local"
    oss_endpoint: str = ""
    oss_region: str = ""
    oss_bucket: str = ""
    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""
    redis_url: str = "redis://127.0.0.1:6379/0"
    tts_secret_id: str = ""
    tts_secret_key: str = ""
    tts_voice_type: int = 101050
    tts_daily_budget: int = 2000
    image_limit_mb: int = 10
    audio_limit_mb: int = 50
    archive_limit_mb: int = 100
    archive_expanded_limit_mb: int = 500
    import_card_limit: int = 50

    @model_validator(mode="after")
    def validate_secrets(self):
        """Reject unusable encryption and unsafe production storage/configuration."""
        Fernet(self.field_encryption_key.encode())
        if len(self.lookup_key) < 32:
            raise ValueError("lookup key must contain at least 32 characters")
        if self.environment == "production":
            if not self.database_url.startswith("mysql+pymysql://"):
                raise ValueError("production requires MySQL")
            if not self.cookie_secure or self.storage_backend != "oss":
                raise ValueError("production requires secure cookies and private OSS")
            if not self.wechat_app_id or not self.wechat_app_secret:
                raise ValueError("production requires the actual WeChat application credentials")
        return self
