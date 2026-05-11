"""0001 — auth/users/employee_profiles/audit tables baseline.

Slice:  P01-S01-T001 — DB auth baseline
Phase:  P01 Auth + Data Foundation
Purpose: Creates the full auth+profile+audit schema needed by Phase 1.
         9 tables in dependency order (parents before children, FK-safe).
         Includes CHECK constraint, UNIQUE constraints, and indexes for
         token lookup and audit queries.

Tables created (upgrade order):
  1. users               — primary identity + credentials
  2. employee_profiles   — org metadata (1:1 user, FK CASCADE)
  3. roles               — RBAC role names
  4. permissions         — fine-grained permission keys
  5. user_roles          — join table users x roles (composite PK, FK CASCADE)
  6. refresh_tokens      — JWT refresh token lifecycle (FK CASCADE)
  7. mfa_totp_secrets    — encrypted TOTP secrets (1:1 user, FK CASCADE)
  8. password_reset_tokens — password reset one-time tokens (FK CASCADE)
  9. audit_logs          — compliance audit trail (FK SET NULL — GDPR Art. 30)

Tables dropped (downgrade order — reverse, children before parents).
pgcrypto extension NOT dropped (D2: idempotent, may be used by future migrations).

Decisions implemented:
  D1: NO vector extension here (belongs to P02-S01-T001)
  D2: NO DROP EXTENSION pgcrypto in downgrade (idempotent, future-safe)
  D6: refresh_tokens.user_id and password_reset_tokens.user_id declared NOT NULL
  D7: indexes for token hash lookup and audit queries
  D8: NO index on employee_profiles.country (YAGNI)
  D9: NO seed of roles/permissions data here
  D10: NO trigger for updated_at (app-controlled P01-S02-T007)

Revises: (none — first migration)
Create Date: 2026-05-11

Source refs:
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3#users
  - docs/source-of-truth/instrucciones.md §3.1#auth-perfiles
  - 01-non-negotiables.md §Database, §Security/Audit log (GDPR Art. 17 + Art. 30)
"""

from __future__ import annotations

import logging

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID, JSONB

logger = logging.getLogger("alembic.runtime.migration")

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Create all auth/profile/audit tables in FK-safe order.

    Creates pgcrypto extension first (IF NOT EXISTS — idempotent), then
    tables in parent-before-child order to satisfy FK constraints.
    Indexes are created immediately after each table that needs them.
    """
    logger.info("0001.upgrade.start: creating pgcrypto extension and 9 auth tables")

    # ------------------------------------------------------------------
    # 0. PostgreSQL extension — pgcrypto for gen_random_uuid()
    # ------------------------------------------------------------------
    # gen_random_uuid() requires pgcrypto (§4.1). IF NOT EXISTS is idempotent.
    # NOT dropped in downgrade (D2) — standard practice for shared extensions.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    logger.info("0001.upgrade: pgcrypto extension ensured")

    # ------------------------------------------------------------------
    # 1. users — primary identity table
    # ------------------------------------------------------------------
    logger.info("0001.upgrade: creating table users")
    op.create_table(
        "users",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("full_name", sa.Text, nullable=False),
        sa.Column(
            "status",
            sa.Text,
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "preferred_language",
            sa.Text,
            nullable=False,
            server_default=sa.text("'es'"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Named constraints so Alembic downgrade can find them by name
        sa.UniqueConstraint("email", name="users_email_key"),
        sa.CheckConstraint(
            "preferred_language IN ('es','en','fr')",
            name="users_language_chk",
        ),
    )
    logger.info("0001.upgrade: table users created")

    # ------------------------------------------------------------------
    # 2. employee_profiles — org metadata (1:1 user, FK -> users CASCADE)
    # ------------------------------------------------------------------
    logger.info("0001.upgrade: creating table employee_profiles")
    op.create_table(
        "employee_profiles",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                ondelete="CASCADE",
                name="employee_profiles_user_id_fkey",
            ),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("employee_id", sa.Text, nullable=False),
        sa.Column("brand", sa.Text, nullable=False),
        sa.Column("society", sa.Text, nullable=False),
        sa.Column("center", sa.Text, nullable=False),
        sa.Column("country", sa.Text, nullable=False),
        sa.Column("department", sa.Text, nullable=False),
        sa.Column(
            "metadata",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.UniqueConstraint("employee_id", name="employee_profiles_employee_id_key"),
    )
    logger.info("0001.upgrade: table employee_profiles created")

    # ------------------------------------------------------------------
    # 3. roles — RBAC role names
    # ------------------------------------------------------------------
    logger.info("0001.upgrade: creating table roles")
    op.create_table(
        "roles",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.UniqueConstraint("name", name="roles_name_key"),
    )
    logger.info("0001.upgrade: table roles created")

    # ------------------------------------------------------------------
    # 4. permissions — fine-grained permission keys
    # ------------------------------------------------------------------
    logger.info("0001.upgrade: creating table permissions")
    op.create_table(
        "permissions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("key", sa.Text, nullable=False),
        sa.UniqueConstraint("key", name="permissions_key_key"),
    )
    logger.info("0001.upgrade: table permissions created")

    # ------------------------------------------------------------------
    # 5. user_roles — join table users x roles (composite PK, FK CASCADE)
    # ------------------------------------------------------------------
    logger.info("0001.upgrade: creating table user_roles")
    op.create_table(
        "user_roles",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="user_roles_user_id_fkey"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "role_id",
            UUID(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="CASCADE", name="user_roles_role_id_fkey"),
            primary_key=True,
            nullable=False,
        ),
    )
    # Index on role_id for "list all users with role X" queries (D7).
    # PK covers (user_id, role_id) but NOT role_id alone.
    op.create_index("user_roles_role_id_idx", "user_roles", ["role_id"])
    logger.info("0001.upgrade: table user_roles + role_id index created")

    # ------------------------------------------------------------------
    # 6. refresh_tokens — JWT refresh token lifecycle
    # ------------------------------------------------------------------
    logger.info("0001.upgrade: creating table refresh_tokens")
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                ondelete="CASCADE",
                name="refresh_tokens_user_id_fkey",
            ),
            nullable=False,  # D6: NOT NULL — token without user is invalid
        ),
        sa.Column("token_hash", sa.Text, nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    # Index for O(log n) lookup by refresh endpoint (D7)
    op.create_index("refresh_tokens_token_hash_idx", "refresh_tokens", ["token_hash"])
    # Composite index for "list active tokens for user X" (D7)
    op.create_index(
        "refresh_tokens_user_id_revoked_at_idx",
        "refresh_tokens",
        ["user_id", "revoked_at"],
    )
    logger.info("0001.upgrade: table refresh_tokens + indexes created")

    # ------------------------------------------------------------------
    # 7. mfa_totp_secrets — encrypted TOTP 2FA secrets (1:1 user)
    # ------------------------------------------------------------------
    logger.info("0001.upgrade: creating table mfa_totp_secrets")
    op.create_table(
        "mfa_totp_secrets",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                ondelete="CASCADE",
                name="mfa_totp_secrets_user_id_fkey",
            ),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("secret_encrypted", sa.Text, nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    logger.info("0001.upgrade: table mfa_totp_secrets created")

    # ------------------------------------------------------------------
    # 8. password_reset_tokens — password reset one-time tokens
    # ------------------------------------------------------------------
    logger.info("0001.upgrade: creating table password_reset_tokens")
    op.create_table(
        "password_reset_tokens",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                ondelete="CASCADE",
                name="password_reset_tokens_user_id_fkey",
            ),
            nullable=False,  # D6: NOT NULL — reset token without user is invalid
        ),
        sa.Column("token_hash", sa.Text, nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("used_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    # Index for O(log n) lookup by reset endpoint (D7)
    op.create_index(
        "password_reset_tokens_token_hash_idx",
        "password_reset_tokens",
        ["token_hash"],
    )
    logger.info("0001.upgrade: table password_reset_tokens + index created")

    # ------------------------------------------------------------------
    # 9. audit_logs — compliance audit trail (GDPR Art. 30)
    # ------------------------------------------------------------------
    # actor_user_id ON DELETE SET NULL: audit record is preserved when a user
    # is deleted (GDPR Art. 30 "records of processing"). Pseudonymization
    # (SHA-256 hash + salt) applied by account-deletion service, not here.
    # entity_type + entity_id are polymorphic — no FK (consistency at app layer).
    logger.info("0001.upgrade: creating table audit_logs")
    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                ondelete="SET NULL",
                name="audit_logs_actor_user_id_fkey",
            ),
            nullable=True,  # NULL = system action or after user deletion
        ),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("entity_type", sa.Text, nullable=True),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "metadata",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # Indexes for admin audit page P04-S03-T001 queries (D7)
    op.create_index(
        "audit_logs_actor_created_idx",
        "audit_logs",
        ["actor_user_id", "created_at"],
    )
    op.create_index(
        "audit_logs_entity_idx",
        "audit_logs",
        ["entity_type", "entity_id"],
    )
    op.create_index("audit_logs_created_at_idx", "audit_logs", ["created_at"])
    logger.info("0001.upgrade: table audit_logs + indexes created")

    logger.info("0001.upgrade.done: 9 tables + pgcrypto extension ready")


def downgrade() -> None:
    """Drop all tables created by this migration in reverse FK order.

    Order (children before parents to satisfy FK constraints):
      audit_logs -> password_reset_tokens -> mfa_totp_secrets ->
      refresh_tokens -> user_roles -> permissions -> roles ->
      employee_profiles -> users.

    pgcrypto extension is NOT dropped (D2): idempotent to keep; dropping it
    would risk breaking other database objects that use gen_random_uuid().
    Standard Alembic practice: only drop extensions owned 100% by this migration.
    """
    logger.info("0001.downgrade.start: dropping 9 auth tables in reverse FK order")

    # 9. audit_logs
    logger.info("0001.downgrade: dropping audit_logs")
    op.drop_index("audit_logs_created_at_idx", table_name="audit_logs")
    op.drop_index("audit_logs_entity_idx", table_name="audit_logs")
    op.drop_index("audit_logs_actor_created_idx", table_name="audit_logs")
    op.drop_table("audit_logs")

    # 8. password_reset_tokens
    logger.info("0001.downgrade: dropping password_reset_tokens")
    op.drop_index("password_reset_tokens_token_hash_idx", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")

    # 7. mfa_totp_secrets
    logger.info("0001.downgrade: dropping mfa_totp_secrets")
    op.drop_table("mfa_totp_secrets")

    # 6. refresh_tokens
    logger.info("0001.downgrade: dropping refresh_tokens")
    op.drop_index("refresh_tokens_user_id_revoked_at_idx", table_name="refresh_tokens")
    op.drop_index("refresh_tokens_token_hash_idx", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    # 5. user_roles
    logger.info("0001.downgrade: dropping user_roles")
    op.drop_index("user_roles_role_id_idx", table_name="user_roles")
    op.drop_table("user_roles")

    # 4. permissions
    logger.info("0001.downgrade: dropping permissions")
    op.drop_table("permissions")

    # 3. roles
    logger.info("0001.downgrade: dropping roles")
    op.drop_table("roles")

    # 2. employee_profiles
    logger.info("0001.downgrade: dropping employee_profiles")
    op.drop_table("employee_profiles")

    # 1. users
    logger.info("0001.downgrade: dropping users")
    op.drop_table("users")

    # NOTE: pgcrypto extension is intentionally NOT dropped here (D2).
    logger.info("0001.downgrade.done: 9 tables dropped; pgcrypto extension kept (D2)")
