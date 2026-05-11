"""
Hilo People — SQLAlchemy 2.x ORM models: auth session and audit.

Slice:  P01-S01-T001 — 0001_auth_users_employee_audit migration
Phase:  P01 Auth + Data Foundation
Purpose: Defines ORM models for authentication session management and audit:
         RefreshToken, MfaTotpSecret, PasswordResetToken, AuditLog.

Bounded context: credentials/session/audit — token lifecycle, 2FA secrets,
password reset flow, and compliance audit trail. Identity models live in user.py.

Mapped tables (all created by migration 0001_auth_users_employee_audit.py):
  - refresh_tokens        (FK -> users ON DELETE CASCADE)
  - mfa_totp_secrets      (FK -> users ON DELETE CASCADE, 1:1)
  - password_reset_tokens (FK -> users ON DELETE CASCADE)
  - audit_logs            (FK -> users ON DELETE SET NULL — GDPR Art. 30)

Key deps:
  - app.db.base        — Base (DeclarativeBase with naming_convention)
  - sqlalchemy==2.0.49 (Mapped, mapped_column, relationship, ForeignKey)
  - sqlalchemy.dialects.postgresql — UUID, JSONB

Source refs:
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3#users
  - docs/source-of-truth/instrucciones.md §3.1#auth-perfiles
  - 01-non-negotiables.md §Security/Audit log (GDPR Art. 17 + Art. 30)

Decisions implemented:
  - D3: session/audit in auth.py (bounded context)
  - D6: user_id NOT NULL on refresh_tokens and password_reset_tokens
        (tighter than §10.3 raw DDL; tokens without user have no meaning)
  - D7: recommended indexes for token lookup and audit queries

Note on column name 'metadata':
  SQLAlchemy reserves 'metadata' as a class-level attribute on mapped classes.
  The Python attribute is named 'extra_metadata' with mapped_column(name='metadata')
  so the DB column name matches §10.3 exactly.
"""

from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


# ---------------------------------------------------------------------------
# RefreshToken — JWT refresh token lifecycle
# ---------------------------------------------------------------------------
class RefreshToken(Base):
    """ORM model for the `refresh_tokens` table.

    Stores hashed refresh tokens for JWT rotation (§10.2 Auth strategy).
    token_hash is the hash of the opaque token issued to the client via
    HttpOnly cookie. Tokens rotate on each use (P01-S02-T003).

    revoked_at NULL = token is active; non-NULL = revoked (logout/rotate).
    expires_at enforced at application layer (P01-S02-T003 repository).

    user_id is NOT NULL (D6): a token without a user is semantically invalid.

    Table: refresh_tokens
    PK: id UUID (gen_random_uuid())
    FK: user_id -> users.id ON DELETE CASCADE (NOT NULL per D6)
    Indexes: token_hash (for validate-refresh lookup), (user_id, revoked_at)

    Refs: §10.3, §10.2, instrucciones.md §3.1 (refresh tokens hasheados y rotan)
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE", name="refresh_tokens_user_id_fkey"),
        nullable=False,
        comment="FK -> users.id ON DELETE CASCADE; NOT NULL (D6 — token without user is invalid)",
    )
    token_hash: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Hashed opaque token — NEVER log the raw token value",
    )
    expires_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        comment="Expiration timestamp; enforced at app layer P01-S02-T003",
    )
    revoked_at: Mapped[sa.DateTime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
        comment="NULL = active; non-NULL = revoked (logout or rotation)",
    )


# ---------------------------------------------------------------------------
# MfaTotpSecret — TOTP 2FA secret (1:1 with User)
# ---------------------------------------------------------------------------
class MfaTotpSecret(Base):
    """ORM model for the `mfa_totp_secrets` table.

    Stores Fernet-encrypted TOTP secrets for 2FA. user_id is PK (1:1 with
    users). If user rotates 2FA, the same row is UPDATEd — not a new INSERT.

    secret_encrypted is the Fernet-encrypted base32 TOTP seed. Encryption key
    lives in env var MFA_ENCRYPTION_KEY (P02-S02-T001 Security service).

    enabled=False means 2FA configured but not yet activated. Admin users must
    have enabled=True (enforced at app layer, not at schema level).

    Table: mfa_totp_secrets
    PK: user_id UUID (FK -> users.id ON DELETE CASCADE)

    Refs: §10.3, instrucciones.md §3.1 (2FA obligatorio para administradores
          enforced at app layer), non-negotiables §Security (Fernet encryption)
    """

    __tablename__ = "mfa_totp_secrets"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE", name="mfa_totp_secrets_user_id_fkey"),
        primary_key=True,
        nullable=False,
        comment="PK + FK -> users.id ON DELETE CASCADE; 1:1 with users",
    )
    secret_encrypted: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Fernet-encrypted base32 TOTP seed — NEVER log in plain text",
    )
    enabled: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("false"),
        comment="False = 2FA configured but not yet activated by the user",
    )


# ---------------------------------------------------------------------------
# PasswordResetToken — password reset flow one-time token
# ---------------------------------------------------------------------------
class PasswordResetToken(Base):
    """ORM model for the `password_reset_tokens` table.

    Stores hashed one-time tokens for the forgot-password / reset-password
    flow (P01-S02-T005 endpoint).

    token_hash is the hash of the URL-safe token emailed to the user.
    used_at NULL = token not yet consumed; non-NULL = already used.
    Expiry enforced at application layer.

    user_id is NOT NULL (D6): a reset token without a user is invalid.

    Table: password_reset_tokens
    PK: id UUID (gen_random_uuid())
    FK: user_id -> users.id ON DELETE CASCADE (NOT NULL per D6)
    Index: token_hash (for fast lookup by reset endpoint)

    Refs: §10.3, instrucciones.md §3.1
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "users.id",
            ondelete="CASCADE",
            name="password_reset_tokens_user_id_fkey",
        ),
        nullable=False,
        comment="FK -> users.id ON DELETE CASCADE; NOT NULL (D6 — reset token without user is invalid)",
    )
    token_hash: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Hash of the URL-safe one-time reset token — NEVER log raw token",
    )
    expires_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        comment="Expiration enforced at app layer P01-S02-T005",
    )
    used_at: Mapped[sa.DateTime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
        comment="NULL = token available; non-NULL = already consumed",
    )


# ---------------------------------------------------------------------------
# AuditLog — compliance audit trail (GDPR Art. 30)
# ---------------------------------------------------------------------------
class AuditLog(Base):
    """ORM model for the `audit_logs` table.

    Immutable audit trail for all sensitive actions (§Security/Audit log).
    Retained indefinitely per GDPR Art. 30. When a user exercises the right
    to erasure (GDPR Art. 17), actor_user_id is set to NULL (ON DELETE SET NULL),
    preserving the row; pseudonymization (SHA-256 + salt) is applied by the
    account-deletion service (future slice P04), not here.

    actor_user_id is NULLABLE (intentional — differs from refresh_tokens D6):
    - ON DELETE SET NULL preserves audit record when user is deleted.
    - System/automated actions may have actor_user_id=NULL.

    entity_type + entity_id are polymorphic. No FK constraint because the
    entity may be from any table; referential consistency is at app layer.

    The Python attribute 'extra_metadata' maps to DB column 'metadata' to avoid
    conflict with SQLAlchemy's class-level 'metadata' attribute.

    Table: audit_logs
    PK: id UUID (gen_random_uuid())
    FK: actor_user_id -> users.id ON DELETE SET NULL (nullable)
    Indexes: (actor_user_id, created_at), (entity_type, entity_id), (created_at)

    Refs: §10.3, 01-non-negotiables.md §Security/Audit log
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "users.id",
            ondelete="SET NULL",
            name="audit_logs_actor_user_id_fkey",
        ),
        nullable=True,
        comment=(
            "FK -> users.id ON DELETE SET NULL. NULL after user deletion "
            "(GDPR Art. 17 erasure); pseudonymize in account-deletion service."
        ),
    )
    action: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Audit action name e.g. 'user.login', 'user.password_reset'",
    )
    entity_type: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="Polymorphic entity type e.g. 'user', 'ai_provider' (no FK)",
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Polymorphic entity PK; consistency enforced at app layer",
    )
    # DB column name is 'metadata'; Python attribute is 'extra_metadata' to
    # avoid conflict with SQLAlchemy's class-level 'metadata' attribute.
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        comment="Contextual metadata (ip, user_agent, request_id, etc.); DB col: 'metadata'",
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        comment="Immutable creation timestamp; audit records have no updated_at",
    )
