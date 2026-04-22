"""
Centralized configuration management using Pydantic Settings
"""

import os
import secrets
from pathlib import Path
from typing import Optional, Set
from pydantic_settings import BaseSettings, SettingsConfigDict
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
    cors_origins: list = Field(
        default_factory=lambda: ["*"], description="Allowed CORS origins"
    )

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

    # Database settings — supports SQLite and PostgreSQL
    # For PostgreSQL: postgresql://user:password@localhost:5432/dbname
    # For SQLite: sqlite:///screenrecorder.db
    database_url: str = Field(
        default="sqlite:///screenrecorder.db",
        alias="DATABASE_URL",
        description="Database connection URL (SQLite or PostgreSQL)",
    )

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = Field(default=60)
    rate_limit_storage_uri: Optional[str] = Field(
        default=None,
        description="Redis URI for distributed rate limiting (e.g. redis://localhost:6379/0). "
        "If not set, falls back to in-memory rate limiting.",
    )

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # HTTPS settings
    ssl_enabled: bool = False
    ssl_cert: Optional[str] = None
    ssl_key: Optional[str] = None
    enforce_https: bool = Field(
        default=False, description="Enforce HTTPS redirects in production"
    )

    # Retention & cleanup policies
    audit_log_retention_days: int = Field(
        default=90,
        description="Delete audit logs older than this many days (0 = keep forever)",
    )
    video_retention_days: int = Field(
        default=0,
        description="Delete videos older than this many days (0 = keep forever)",
    )
    video_disk_limit_mb: int = Field(
        default=0,
        description="Max total video storage in MB before auto-cleanup (0 = no limit)",
    )

    # Private key encryption
    key_passphrase: Optional[str] = Field(
        default=None,
        description="Passphrase to encrypt the RSA private key at rest. "
        "If set, private_key.pem will be encrypted with AES-256-CBC.",
    )

    @field_validator("admin_password")
    @classmethod
    def validate_admin_password(cls, v: str) -> str:
        # Known insecure defaults that must be changed in production
        insecure_defaults = {
            "changeme123456",
            "admin12345678",
            "password123456",
        }
        if not v or v in insecure_defaults:
            import warnings

            warnings.warn(
                "ADMIN_PASSWORD is set to an insecure default! "
                "Set it via the ADMIN_PASSWORD environment variable for production!",
                UserWarning,
                stacklevel=2,
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


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
