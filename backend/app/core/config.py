"""
Application configuration via pydantic-settings.

Slice: P00-S01-T003 — Backend dependency pack
Phase: P00 — Scaffold + Design System

Reads all env vars from the environment (and from .env if present). Typed fields
declared here for every var listed in HILO_PEOPLE_TECHNICAL_GUIDE.md §11.1 and
the canonical .env.example created in T001.

Dependencies:
  - pydantic-settings 2.14.1
  - pydantic 2.12.5

Security: secrets are typed as SecretStr — they are NEVER logged. Fields with
no safe default are SecretStr(""); the consuming slice (P01-S02-T001 for JWT,
P02-S02-T001 for encryption) adds a startup validator.

Do NOT instantiate DB connections, Redis clients, or HTTP sessions here.
"""
from __future__ import annotations

import logging
import os

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_logger = logging.getLogger(__name__)

_VERBOSE = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() in ("1", "true", "yes")


class Settings(BaseSettings):
    """Application settings loaded from environment.

    Fields map 1:1 to the canonical .env.example vars declared in T001.
    Secrets are SecretStr to prevent accidental logging.

    Purpose: central config store consumed by every feature module.
    Errors: pydantic ValidationError if a required field is missing at runtime.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server
    api_host: str = Field("127.0.0.1", description="Backend bind host.")
    api_port: int = Field(8000, description="Backend bind port.")
    app_version: str = Field("0.0.0", description="App version for /health.")

    # Logging
    enable_verbose_logging: bool = Field(False, description="DEBUG level when true.")
    log_level: str = Field("WARNING", description="Overrides verbose gate when set explicitly.")

    # Database
    database_url: SecretStr = Field(
        SecretStr("postgresql+asyncpg://hilopeople:change-me@localhost:5432/hilopeople_dev"),
        description="PostgreSQL async DSN. Used by P01-S01-T001+.",
    )

    # Redis / Celery
    redis_url: SecretStr = Field(
        SecretStr("redis://localhost:6379/0"),
        description="Redis URL for Celery broker + cache.",
    )
    celery_broker_url: SecretStr = Field(
        SecretStr("redis://localhost:6379/1"),
        description="Celery broker DSN (separate Redis DB).",
    )

    # JWT (consumed in P01-S02-T001)
    jwt_secret: SecretStr = Field(
        SecretStr(""),
        description="HMAC secret for JWT signing. Required in P01-S02-T001.",
    )
    jwt_access_token_ttl_seconds: int = Field(900, description="Access token TTL.")
    jwt_refresh_token_ttl_seconds: int = Field(604800, description="Refresh token TTL.")

    # Encryption (consumed in P02-S02-T001)
    provider_encryption_key: SecretStr = Field(
        SecretStr(""),
        description="Fernet key for credential cipher. Required in P02-S02-T001.",
    )

    # LiteLLM gateway (consumed in P02-S05)
    litellm_master_key: SecretStr = Field(
        SecretStr(""), description="LiteLLM proxy master key."
    )
    litellm_proxy_base_url: str = Field(
        "http://localhost:4000", description="LiteLLM proxy base URL."
    )

    # AWS S3 / MinIO (consumed in P02-S06)
    aws_access_key_id: SecretStr = Field(
        SecretStr(""), description="AWS / MinIO access key ID."
    )
    aws_secret_access_key: SecretStr = Field(
        SecretStr(""), description="AWS / MinIO secret key."
    )
    aws_region: str = Field("eu-west-1", description="AWS region.")
    s3_bucket_rag_documents: str = Field(
        "hilopeople-rag-documents-dev", description="S3 bucket for RAG originals."
    )

    # Email (consumed in P02-S03)
    resend_api_key: SecretStr = Field(
        SecretStr(""), description="Resend API key for transactional email."
    )
    mail_from_address: str = Field(
        "noreply@hilopeople.example.com", description="Sender address."
    )
    mail_from_name: str = Field("Hilo People", description="Sender display name.")

    # CORS
    cors_allowed_origins: str = Field(
        "http://localhost:5173,http://127.0.0.1:5173",
        description="Comma-separated CORS origin whitelist.",
    )

    # i18n (consumed in P00-S01-T005)
    default_language: str = Field("es", description="Fallback locale for i18n.")

    # RAG upload (consumed in P02-S06)
    max_upload_mb: int = Field(50, description="Max upload file size in MB.")

    # MCP security (consumed in P02-S07)
    mcp_allowlist_domains: str = Field(
        "", description="Comma-separated domain whitelist for MCP tool calls."
    )

    # Observability
    sentry_dsn: SecretStr = Field(
        SecretStr(""), description="Sentry DSN for error tracking."
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse cors_allowed_origins into a list of origin strings."""
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


def get_settings() -> Settings:
    """Return the Settings singleton.

    Purpose: lazy factory so tests can override env vars before first call.
    Returns: Settings instance loaded from environment + .env file.
    Errors: pydantic.ValidationError if schema mismatch.
    """
    if _VERBOSE:
        _logger.debug("BEFORE get_settings: loading from environment")
    settings = Settings()  # type: ignore[call-arg]
    if _VERBOSE:
        _logger.debug(
            "AFTER get_settings: loaded (api_host=%s, api_port=%s, verbose=%s)",
            settings.api_host,
            settings.api_port,
            settings.enable_verbose_logging,
        )
    return settings
