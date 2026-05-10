"""
Application configuration via pydantic-settings.

Slice: P01-S01-T004 — Fix .env path resolution + DATABASE_URL host port for native dev
Phase: P01 — Auth + Base Capabilities

Originally created in P00-S01-T003. Field names aligned to TECHNICAL_GUIDE §11.1
in P01-S01-T002 (atomic rename across config + .env + docker-compose + logging).

Key renames (P01-S01-T002):
  - jwt_secret (single HMAC SecretStr) → jwt_private_key + jwt_public_key
    (RS256 asymmetric, per §10.2 + §11.1)
  - provider_encryption_key            → encryption_key
  - litellm_proxy_base_url             → litellm_base_url
  - s3_bucket_rag_documents            → s3_bucket_documents
  - max_upload_mb default 50           → 25 (§11.1 dev/staging/prod)
  - mcp_allowlist_domains default ""   → "localhost" (§11.1 dev)

env_file resolution fix (P01-S01-T004):
  - pydantic-settings 2.14.1 interprets env_file relative to the process cwd at
    Settings() instantiation time. This breaks when pytest/alembic run from
    cd backend/ because there is no .env file there.
  - Fix: resolve _ENV_FILE to an ABSOLUTE path anchored on __file__ so it works
    regardless of cwd. config.py is at backend/app/core/config.py:
      parents[0] = backend/app/core/
      parents[1] = backend/app/
      parents[2] = backend/
      parents[3] = <project_root>  ← .env lives here
  - Real environment variables (set by docker-compose, CI, shell exports) still
    take precedence over the .env file per pydantic-settings priority rules.

Reads all env vars from the environment (and from .env if present). Typed fields
declared here for every var listed in HILO_PEOPLE_TECHNICAL_GUIDE.md §11.1 and
the canonical .env.example created in T001.

Dependencies:
  - pydantic-settings 2.14.1
  - pydantic 2.12.5

Security: secrets are typed as SecretStr — they are NEVER logged. Fields with
no safe default are SecretStr(""); the consuming slice (P01-S02-T001 for JWT,
P02-S02-T001 for encryption) adds a startup validator.

JWT shape (RS256, §10.2 + §11.1): jwt_private_key holds the RSA private key PEM;
jwt_public_key holds the RSA public key PEM. Both are SecretStr to keep them out
of logs; consuming code calls .get_secret_value() when it needs the raw PEM.
No startup validator is added here — deferred to P01-S02-T001 to avoid blocking
the dev stack before keys are provisioned.

Do NOT instantiate DB connections, Redis clients, or HTTP sessions here.
Do NOT log DATABASE_URL — it contains credentials. Log only host+port if needed.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_logger = logging.getLogger(__name__)

_VERBOSE = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() in ("1", "true", "yes")

# Resolve .env to an absolute path anchored from __file__ so it works regardless
# of the process cwd (pytest from cd backend/, alembic from cd backend/,
# uvicorn from project root — all resolve to the same file).
# config.py depth: backend/app/core/config.py → parents[3] = project root.
_PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]
_ENV_FILE: Path = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment.

    Fields map 1:1 to the canonical .env.example vars declared in T001.
    Secrets are SecretStr to prevent accidental logging.

    Purpose: central config store consumed by every feature module.
    Errors: pydantic ValidationError if a required field is missing at runtime.

    env_file is an absolute path (P01-S01-T004 fix) so it resolves correctly
    whether the process cwd is the project root, backend/, or any other directory.
    """

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),  # absolute path — cwd-independent (P01-S01-T004)
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
    log_level: str = Field(
        "WARNING", description="Overrides verbose gate when set explicitly."
    )

    # Database
    # Default DSN for native dev (Mode A): localhost:5433 because docker-compose.yml
    # maps host port 5433 → container port 5432 for hilo-postgres. Port 5432 on the
    # host is occupied by a sibling project's postgres container.
    # Inside compose containers (Mode B), DATABASE_URL is overridden by the
    # docker-compose.yml environment block (postgres:5432) — the .env file value
    # is not used there. See .env.example for the full Mode A / Mode B explanation.
    # NEVER log this value — it contains credentials. Log only host:port/dbname.
    database_url: SecretStr = Field(
        SecretStr("postgresql+asyncpg://hilopeople:change-me@localhost:5433/hilopeople_dev"),
        description="PostgreSQL async DSN. Mode A (native dev) = localhost:5433.",
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

    # JWT — RS256 asymmetric (§10.2 + §11.1, aligned in P01-S01-T002)
    # jwt_private_key: RSA private key PEM for signing access tokens (P01-S02-T001).
    # jwt_public_key:  RSA public key PEM for verifying tokens (P01-S02-T001).
    # Both kept as SecretStr to prevent log leakage; public key is not technically
    # a secret but SecretStr is the least-surprise default — consuming code calls
    # .get_secret_value() when it needs the raw PEM for RS256 verify.
    # No startup validator here — deferred to P01-S02-T001 so the dev stack
    # can start before keypairs are provisioned.
    jwt_private_key: SecretStr = Field(
        SecretStr(""),
        description="RSA private key PEM for JWT RS256 signing. Required in P01-S02-T001.",
    )
    jwt_public_key: SecretStr = Field(
        SecretStr(""),
        description=(
            "RSA public key PEM for JWT RS256 verification. Required in P01-S02-T001."
        ),
    )
    jwt_access_token_ttl_seconds: int = Field(900, description="Access token TTL.")
    jwt_refresh_token_ttl_seconds: int = Field(604800, description="Refresh token TTL.")

    # Encryption (consumed in P02-S02-T001)
    # Renamed from provider_encryption_key → encryption_key in P01-S01-T002 (§11.1).
    encryption_key: SecretStr = Field(
        SecretStr(""),
        description="Fernet key for credential cipher. Required in P02-S02-T001.",
    )

    # LiteLLM gateway (consumed in P02-S05)
    # litellm_proxy_base_url renamed → litellm_base_url in P01-S01-T002 (§11.1).
    # docker-compose.yml backend+worker environment blocks updated in same slice.
    litellm_master_key: SecretStr = Field(
        SecretStr(""), description="LiteLLM proxy master key."
    )
    litellm_base_url: str = Field(
        "http://localhost:4000",
        description="LiteLLM gateway base URL (§11.1 LITELLM_BASE_URL).",
    )

    # AWS S3 / MinIO (consumed in P02-S06)
    aws_access_key_id: SecretStr = Field(
        SecretStr(""), description="AWS / MinIO access key ID."
    )
    aws_secret_access_key: SecretStr = Field(
        SecretStr(""), description="AWS / MinIO secret key."
    )
    aws_region: str = Field("eu-west-1", description="AWS region.")
    # Renamed from s3_bucket_rag_documents → s3_bucket_documents in P01-S01-T002 (§11.1).
    # Default value kept as-is (infra bucket naming is an ops concern, not §11.1).
    s3_bucket_documents: str = Field(
        "hilopeople-rag-documents-dev",
        description="S3 bucket for RAG document originals (§11.1 S3_BUCKET_DOCUMENTS).",
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
    # Default changed 50 → 25 in P01-S01-T002 to match §11.1 dev/staging/prod = 25 MB.
    max_upload_mb: int = Field(25, description="Max upload file size in MB (§11.1: 25).")

    # MCP security (consumed in P02-S07)
    # Default changed "" → "localhost" in P01-S01-T002 to match §11.1 dev = "localhost".
    mcp_allowlist_domains: str = Field(
        "localhost",
        description="Comma-separated domain whitelist for MCP tool calls (§11.1).",
    )

    # Corporate email domains (P01-S02-T001 — sign-up corporate-email rule)
    # Empty default = permissive in dev (allows any domain, including gmail.com).
    # Non-empty = strict allowlist; comma-separated (e.g. "hilo.com,hilopeople.com").
    # Production deployment MUST set this to the company's real domain(s).
    # Source: instrucciones.md §3.1 + task-pack P01-S02-T001 §9 R3.
    # Pattern mirrors cors_allowed_origins: raw str field + list property.
    corporate_email_domains: str = Field(
        "",
        description=(
            "Comma-separated corporate email domain allowlist. "
            "Empty = permissive (dev). Non-empty = strict allowlist. "
            "Env var: CORPORATE_EMAIL_DOMAINS."
        ),
    )

    @property
    def corporate_email_domains_list(self) -> list[str]:
        """Parse CORPORATE_EMAIL_DOMAINS into a list of domain strings.

        Purpose: convenience property; mirrors cors_origins_list pattern.
        Returns: list of lowercase domain strings; empty list when unset/empty.
        """
        return [
            d.strip().lower()
            for d in self.corporate_email_domains.split(",")
            if d.strip()
        ]

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

    env_file is an absolute path (P01-S01-T004 fix); the path is logged at DEBUG
    level so it can be verified in dev. The DSN itself is NEVER logged — it contains
    credentials. Only host:port/dbname are safe to surface in logs.
    """
    if _VERBOSE:
        _logger.debug(
            "BEFORE get_settings: loading Settings (env_file=%s, exists=%s)",
            _ENV_FILE,
            _ENV_FILE.exists(),
        )
    settings = Settings()  # type: ignore[call-arg]
    if _VERBOSE:
        # Extract host:port/dbname from the DSN without logging the password.
        # Format: postgresql+asyncpg://user:password@host:port/dbname
        _dsn = settings.database_url.get_secret_value()
        try:
            _host_part = _dsn.split("@", 1)[1] if "@" in _dsn else "<unparseable>"
        except Exception:  # noqa: BLE001
            _host_part = "<unparseable>"
        _logger.debug(
            "AFTER get_settings: loaded ("
            "api_host=%s, api_port=%s, verbose=%s, db_host_port=%s)",
            settings.api_host,
            settings.api_port,
            settings.enable_verbose_logging,
            _host_part,  # host:port/dbname only — no password
        )
    return settings
