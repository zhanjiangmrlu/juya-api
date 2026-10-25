"""Typed runtime configuration; application secrets never have fallback values."""

from pathlib import Path
from typing import Literal

from cryptography.fernet import Fernet
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="JUYA_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )

    environment: Literal["local", "test", "production"] = "local"
    database_url: str = Field(repr=False)
    expected_database_host: str = "mysql"
    field_encryption_key: str = Field(repr=False)
    lookup_key: str = Field(repr=False)
    wechat_app_id: str = ""
    wechat_app_secret: str = Field(default="", repr=False)
    allowed_origins: list[str] = []
    cookie_secure: bool = True
    session_days: int = 7
    admin_session_hours: int = 12
    media_root: Path = Path("var/media")
    storage_backend: Literal["local", "oss"] = "local"
    oss_endpoint: str = ""
    oss_region: str = ""
    oss_bucket: str = ""
    oss_access_key_id: str = Field(default="", repr=False)
    oss_access_key_secret: str = Field(default="", repr=False)
    redis_url: str = Field(default="redis://127.0.0.1:6379/0", repr=False)
    worker_role: Literal["admin", "mini"] | None = None
    image_role: Literal["admin", "mini"] | None = None
    tts_secret_id: str = Field(default="", repr=False)
    tts_secret_key: str = Field(default="", repr=False)
    tts_voice_type: int = 101050
    tts_codec: Literal["mp3", "wav"] = "mp3"
    tts_daily_budget: int = 2000
    dictionary_path: Path | None = None
    learning_access_activation_ready: bool = False
    feedback_safety_enabled: bool = False
    feedback_safety_url: str = ""
    feedback_safety_token: str = Field(default="", repr=False)
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
        if self.image_role and self.worker_role and self.image_role != self.worker_role:
            raise ValueError("Worker role must match the image role")
        if self.environment == "production":
            if not self.database_url.startswith("mysql+pymysql://"):
                raise ValueError("production requires MySQL")
            if not self.cookie_secure or self.storage_backend != "oss":
                raise ValueError("production requires secure cookies and private OSS")
            if not self.wechat_app_id or not self.wechat_app_secret:
                raise ValueError("production requires the actual WeChat application credentials")
        return self
