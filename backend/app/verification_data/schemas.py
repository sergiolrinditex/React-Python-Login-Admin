"""
Hilo People — Pydantic v2 schemas for verification fixture validation.

Slice:  P00-S02-T003 — Verification data loader and reset
Phase:  P00 Scaffold + Design System
Purpose: Defines strict Pydantic models for each fixture category. These models
         validate incoming JSON before any DB insert. A ValidationError here
         causes exit-code 2 with a human-readable error message listing the
         missing/invalid field.

Key deps:
  - pydantic==2.12.5 (BaseModel, field_validator, model_config, ConfigDict)

Source refs:
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3 DB Schema
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §6.5 Verification Data Contract
  - 01-non-negotiables.md §Production quality (real validations from day 1)
"""

from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class EmployeeProfileFixture(BaseModel):
    """Employee profile metadata fixture — loaded into employee_profiles table."""

    model_config = ConfigDict(strict=False, extra="ignore")

    employee_id: str
    brand: str
    society: str
    center: str
    country: str
    department: str
    metadata: Optional[dict[str, Any]] = None

    @field_validator("employee_id")
    @classmethod
    def employee_id_not_empty(cls, v: str) -> str:
        """Ensure employee_id is a non-empty string."""
        if not v.strip():
            raise ValueError("employee_id must not be blank")
        return v.strip()


class EmployeeUserFixture(BaseModel):
    """Employee user fixture — loaded into users + employee_profiles tables.

    password_plain is stored as-is in the fixture; the loader hashes it with
    Argon2id before inserting into users.password_hash. It is NEVER stored
    in plain text in the DB. See crypto.hash_password().
    """

    model_config = ConfigDict(strict=False, extra="ignore")

    email: EmailStr
    full_name: str
    password_plain: str
    status: Literal["active", "inactive", "pending"] = "active"
    preferred_language: Literal["es", "en", "fr"] = "es"
    employee_profile: EmployeeProfileFixture

    @field_validator("password_plain")
    @classmethod
    def password_not_empty(cls, v: str) -> str:
        """Ensure password placeholder is not blank."""
        if not v.strip():
            raise ValueError("password_plain must not be blank (used for Argon2 hashing)")
        return v


class AdminUserFixture(BaseModel):
    """Admin user fixture — loaded into users table (with admin role).

    password_plain is stored in fixture for Argon2 hashing at load time.
    Never in plain text in the DB. See crypto.hash_password().
    """

    model_config = ConfigDict(strict=False, extra="ignore")

    email: EmailStr
    full_name: str
    password_plain: str
    status: Literal["active", "inactive", "pending"] = "active"
    preferred_language: Literal["es", "en", "fr"] = "es"
    roles: list[str] = ["admin"]

    @field_validator("password_plain")
    @classmethod
    def password_not_empty(cls, v: str) -> str:
        """Ensure password placeholder is not blank."""
        if not v.strip():
            raise ValueError("password_plain must not be blank")
        return v


class MfaSecretFixture(BaseModel):
    """TOTP secret fixture — stored in auth/mfa_primary.json.

    totp_secret is in plain text in the JSON so /verify-slice can generate
    reproducible TOTP codes (§C.7). The loader will encrypt it with Fernet
    (MFA_ENCRYPTION_KEY) when inserting into mfa_totp_secrets.secret_encrypted.
    This table does not exist in this slice (P00-S02-T003); the fixture is
    validated here for completeness; loading is deferred to P01-S01-T001+.
    """

    model_config = ConfigDict(strict=False, extra="ignore")

    user_email_ref: EmailStr
    totp_secret: str  # base32 RFC 6238 — NEVER logged
    enabled: bool = False

    @field_validator("totp_secret")
    @classmethod
    def secret_is_base32(cls, v: str) -> str:
        """Validate TOTP secret looks like a base32 string."""
        import base64
        try:
            # Pad and decode to confirm it is valid base32.
            padded = v + "=" * (-len(v) % 8)
            base64.b32decode(padded, casefold=True)
        except Exception as exc:
            raise ValueError(f"totp_secret must be valid base32: {exc}") from exc
        return v.upper()


class RagCollectionFixture(BaseModel):
    """RAG collection fixture — loaded into rag_collections table."""

    model_config = ConfigDict(strict=False, extra="ignore")

    name: str
    vertical: str
    language: Literal["es", "en", "fr"] = "es"
    enabled: bool = True
    metadata: Optional[dict[str, Any]] = None


class DocumentFixture(BaseModel):
    """Document metadata fixture — loaded into documents table."""

    model_config = ConfigDict(strict=False, extra="ignore")

    title: str
    language: Literal["es", "en", "fr"] = "es"
    source_uri_ref: str
    status: Literal["pending", "indexed", "error"] = "pending"
    collection_ref: str  # references RagCollectionFixture.name


class AiProviderFixture(BaseModel):
    """AI provider fixture — loaded into ai_providers table.

    credential_plain is stored in fixture for encryption at load time.
    Never in plain text in the DB. See crypto.encrypt_secret().
    """

    model_config = ConfigDict(strict=False, extra="ignore")

    name: str
    provider_type: str
    base_url: str
    status: Literal["active", "inactive"] = "active"
    credential_plain: Optional[str] = None  # encrypted at load time


class McpServerFixture(BaseModel):
    """MCP server fixture — loaded into mcp_servers table."""

    model_config = ConfigDict(strict=False, extra="ignore")

    name: str
    transport_type: Literal["http", "stdio", "sse"] = "http"
    endpoint_url: Optional[str] = None
    command: Optional[str] = None
    status: Literal["active", "inactive"] = "active"
    credential_plain: Optional[str] = None  # encrypted at load time


class AgentFixture(BaseModel):
    """Agent fixture — loaded into agents table."""

    model_config = ConfigDict(strict=False, extra="ignore")

    name: str
    description: str
    enabled: bool = True
    config_jsonb: Optional[dict[str, Any]] = None


class ConversationFixture(BaseModel):
    """Conversation fixture for history group — references users.email."""

    model_config = ConfigDict(strict=False, extra="ignore")

    user_email_ref: EmailStr
    language: Literal["es", "en", "fr"] = "es"
    title: str
    messages: list[dict[str, Any]] = []
