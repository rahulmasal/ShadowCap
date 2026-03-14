"""
Centralized configuration management using Pydantic Settings
"""

import os
import secrets
from pathlib import Path
from typing import Optional, Set
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # Server settings
    host: str = "0.0.0.0"
    port: int = Field(default=5000, ge=1, le=65535)
    debug: bool = False

    # Security settings
    secret_key: str = Field(default_factory=lambda: secrets.token_hex(32))
    admin_password: str = Field(default="changeme123456")  # Should be set via env
    session_timeout: int = Field(default=3600, description="Session timeout in seconds")

    # File paths
    upload_folder: Path = Field(default=Path("uploads"))
    license_folder: Path = Field(default=Path("licenses"))
    keys_folder: Path = Field(default=Path("keys"))
    clients_folder: Path = Field(default=Path("clients"))

    # Upload settings
    max_content_length: int = Field(
        default=500 * 1024 * 1024, description="Max upload size in bytes"
    )
    allowed_extensions: Set[str] = Field(default={"mp4", "avi", "mov", "mkv"})

    # Database settings
    database_url: str = Field(default="sqlite:///screenrecorder.db")

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = Field(default=60)

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # HTTPS settings
    ssl_enabled: bool = False
    ssl_cert: Optional[str] = None
    ssl_key: Optional[str] = None

    @field_validator("admin_password")
    @classmethod
    def validate_admin_password(cls, v: str) -> str:
        if not v or v == "changeme123456":
            import warnings

            warnings.warn(
                "ADMIN_PASSWORD should be set via environment variable for production!",
                UserWarning,
            )
        if len(v) < 12:
            raise ValueError("ADMIN_PASSWORD must be at least 12 characters!")
        return v

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if not v or v == "your-secret-key-change-in-production":
            return secrets.token_hex(32)
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance - lazy initialization
_settings = None


def get_settings() -> Settings:
    """Get settings instance with lazy initialization"""
    global _settings
    if _settings is None:
        _settings = Settings()
        # Ensure directories exist
        for folder in [
            _settings.upload_folder,
            _settings.license_folder,
            _settings.keys_folder,
            _settings.clients_folder,
        ]:
            folder.mkdir(parents=True, exist_ok=True)
    return _settings


# For backward compatibility
settings = get_settings()
