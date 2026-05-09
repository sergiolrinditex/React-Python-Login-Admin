"""
SQLAlchemy ORM models: Role, Permission, RefreshToken, MfaTotpSecret,
PasswordResetToken, and AuditLog.

Slice: P01-S01-T001 — DB auth baseline
Phase: P01 — Auth + base capabilities

Tables declared here:
  - roles             — lookup table for named roles (HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3 line 96)
  - permissions       — lookup table for permission keys (§10.3 line 97)
  - refresh_tokens    — per-user rotating refresh tokens (§10.3 line 99)
  - mfa_totp_secrets  — per-user encrypted TOTP secret (§10.3 line 100)
  - password_reset_tokens — one-time reset tokens (§10.3 line 101)
  - audit_logs        — compliance audit trail (§10.3 lines 103-111)

ON DELETE semantics (per §10.3 + task-pack §12.2):
  - refresh_tokens.user_id          → ON DELETE CASCADE
  - mfa_totp_secrets.user_id        → ON DELETE CASCADE
  - password_reset_tokens.user_id   → ON DELETE CASCADE
  - audit_logs.actor_user_id        → ON DELETE SET NULL  (audit entries survive user deletion;
                                     pseudonymisation per GDPR Art. 17 in a service layer)

Discrepancy D1 (task-pack §6):
  TECHNICAL_GUIDE §10.3 defines audit_logs with columns:
    actor_user_id, action, entity_type, entity_id, metadata, created_at
  01-non-negotiables.md §Audit log mandates:
    user_id, action, resource, timestamp, ip, user_agent, metadata, request_id
  Decision: implement §10.3 verbatim (source-of-truth wins for migration shape).
  The non-negotiable fields (ip, user_agent, request_id) land in a medium follow-up
  that amends §10.3 + adds non-destructive ADD COLUMN migration before P02-S02-T001.

No logging here — pure SQLAlchemy declarative module. See task-pack §8
for the explicit exemption (same pattern as presentational components).

Dependencies:
  - sqlalchemy 2.0.49
  - app.db.models.base.Base
  - app.db.models.user.User (FK target)
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User


class Role(Base):
    """ORM model for the `roles` lookup table.

    Table: roles (HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3 line 96)
    Slice: P01-S01-T001

    Simple lookup table: id (UUID PK) + name (unique TEXT).
    Role assignment lives in user_roles (see user.py).
    """

    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
        doc="Primary key.",
    )
    name: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        unique=True,
        doc="Role identifier (e.g. 'admin', 'employee', 'auditor').",
    )


class Permission(Base):
    """ORM model for the `permissions` lookup table.

    Table: permissions (HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3 line 97)
    Slice: P01-S01-T001

    Simple lookup table: id (UUID PK) + key (unique TEXT permission string).
    """

    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
        doc="Primary key.",
    )
    key: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        unique=True,
        doc="Permission identifier key (e.g. 'chat:read', 'admin:write').",
    )


class RefreshToken(Base):
    """ORM model for the `refresh_tokens` table.

    Table: refresh_tokens (HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3 line 99)
    Slice: P01-S01-T001

    Stores hashed refresh tokens (never plain-text).  Tokens rotate on each
    refresh (see P01-S02-T003).  Revocation is a soft-delete (revoked_at).

    ON DELETE: user_id → CASCADE (tokens disappear when user is deleted).

    Partial index on (expires_at WHERE revoked_at IS NULL) allows efficient
    janitor sweeps of expired active tokens (task-pack §7.2).
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
        doc="Primary key.",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        doc="FK to users(id). ON DELETE CASCADE.",
    )
    token_hash: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        doc="SHA-256 hash of the actual refresh token cookie value.",
    )
    expires_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        doc="Absolute expiry timestamp (UTC).",
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
        doc="Soft-revocation timestamp; NULL means token is still active.",
    )

    user: Mapped[User] = relationship(  # type: ignore[name-defined]
        "User",
        back_populates="refresh_tokens",
    )


class MfaTotpSecret(Base):
    """ORM model for the `mfa_totp_secrets` table.

    Table: mfa_totp_secrets (HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3 line 100)
    Slice: P01-S01-T001

    1:1 per user.  user_id is both PK and FK (ON DELETE CASCADE).

    secret_encrypted is TEXT (Fernet-encrypted TOTP seed).  The encryption
    service lands in P02-S02-T001.

    enabled=False means the TOTP flow has not been completed/confirmed yet.
    """

    __tablename__ = "mfa_totp_secrets"

    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        doc="FK to users(id). ON DELETE CASCADE. 1:1 with User.",
    )
    secret_encrypted: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        doc="Fernet-encrypted TOTP base32 secret. Decryption in P02-S02-T001.",
    )
    enabled: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("false"),
        doc="True once user has confirmed the TOTP enrollment.",
    )

    user: Mapped[User] = relationship(  # type: ignore[name-defined]
        "User",
        back_populates="mfa_totp_secret",
    )


class PasswordResetToken(Base):
    """ORM model for the `password_reset_tokens` table.

    Table: password_reset_tokens (HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3 line 101)
    Slice: P01-S01-T001

    Stores hashed one-time reset tokens.  used_at marks consumption (one-use
    semantics enforced in the service layer, P01-S02-T005).

    ON DELETE: user_id → CASCADE.
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
        doc="Primary key.",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        doc="FK to users(id). ON DELETE CASCADE.",
    )
    token_hash: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        doc="SHA-256 hash of the actual reset token sent by email.",
    )
    expires_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        doc="Absolute expiry timestamp (UTC).",
    )
    used_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
        doc="Timestamp when the token was consumed; NULL = unused.",
    )

    user: Mapped[User] = relationship(  # type: ignore[name-defined]
        "User",
        back_populates="password_reset_tokens",
    )


class AuditLog(Base):
    """ORM model for the `audit_logs` table.

    Table: audit_logs (HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3 lines 103-111)
    Slice: P01-S01-T001

    Compliance audit trail for sensitive actions.

    D1 DECISION (task-pack §6 + handoff ##Discrepancies):
      This migration implements §10.3 verbatim:
        actor_user_id, action, entity_type, entity_id, metadata, created_at
      The 01-non-negotiables.md §Audit log fields (ip, user_agent, request_id)
      will arrive via a non-destructive ADD COLUMN medium follow-up before
      P02-S02-T001 (security/audit middleware).

    ON DELETE: actor_user_id → SET NULL.
      Audit entries survive user deletion. GDPR Art. 17 pseudonymisation
      (hash SHA-256 of user_id with salt) is a service-layer responsibility,
      not a migration constraint.

    entity_type / entity_id: nullable (some audit events are not entity-bound).
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
        doc="Primary key.",
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        doc="FK to users(id). ON DELETE SET NULL — audit survives user deletion.",
    )
    action: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        doc="Action identifier (e.g. 'auth.login', 'password.reset').",
    )
    entity_type: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        doc="Type of the affected entity (e.g. 'user', 'ai_provider').",
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.UUID(as_uuid=True),
        nullable=True,
        doc="ID of the affected entity; NULL for global/system actions.",
    )
    metadata_col: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="JSONB bag for action-specific context (no PII, no secrets).",
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        doc="Event timestamp (UTC); immutable after creation.",
    )

    actor_user: Mapped[User | None] = relationship(  # type: ignore[name-defined]
        "User",
        back_populates="audit_logs_acted",
        foreign_keys=[actor_user_id],
    )
