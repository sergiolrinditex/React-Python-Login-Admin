"""Auth / profile / audit baseline schema.

Revision ID: 0001
Revises: None
Create Date: 2026-05-09 12:00:00.000000 UTC

Slice: P01-S01-T001 — DB auth baseline
Phase: P01 — Auth + base capabilities

Tables created (in dependency order):
  1. users                 — core identity
  2. employee_profiles     — 1:1 extension (FK users.id CASCADE)
  3. roles                 — lookup
  4. permissions           — lookup
  5. user_roles            — M:N association (FK users + roles CASCADE)
  6. refresh_tokens        — per-user rotating tokens (FK users CASCADE)
  7. mfa_totp_secrets      — per-user TOTP secret (FK users CASCADE)
  8. password_reset_tokens — one-time reset tokens (FK users CASCADE)
  9. audit_logs            — compliance trail (FK users SET NULL)

Extensions (idempotent CREATE IF NOT EXISTS):
  - pgcrypto  — provides gen_random_uuid() (backward compat with pg<13)
  - vector    — pgvector foundation (consumed by P02-S01-T001)

Explicit indexes (task-pack §7.2 + 01-non-negotiables.md §Database):
  - user_roles_role_id_idx                — reverse join (role→users)
  - refresh_tokens_user_id_idx            — per-user enumeration
  - refresh_tokens_active_expires_idx     — partial (WHERE revoked_at IS NULL), janitor sweep
  - password_reset_tokens_user_id_idx     — per-user lookup
  - password_reset_tokens_expires_idx     — janitor sweep
  - audit_logs_actor_created_idx          — per-actor newest-first
  - audit_logs_created_idx                — global newest-first
  - audit_logs_entity_idx                 — entity-type + entity-id lookup

Discrepancy D1 (audit_logs columns):
  §10.3 schema wins for initial migration.  Non-negotiable §Audit log fields
  (ip, user_agent, request_id) arrive via ADD COLUMN in a follow-up slice
  before P02-S02-T001.  See handoff P01-S01-T001.md §Discrepancies.

Downgrade discipline (task-pack §7.3):
  Drop indexes → drop tables in reverse dependency order (children first).
  Extensions NOT dropped (other tools may rely on them; CREATE IF NOT EXISTS
  is idempotent on re-upgrade).

Source: HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3 (lines 70-111)
Task-pack P01-S01-T001 §7
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# ---------------------------------------------------------------------------
# revision identifiers
# ---------------------------------------------------------------------------
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create extensions, tables and indexes for the auth baseline schema."""

    # ------------------------------------------------------------------
    # Extensions (idempotent)
    # ------------------------------------------------------------------
    # pgcrypto: provides gen_random_uuid() for UUID primary keys.
    # Technically pg18 ships this natively, but the §10.3 baseline declares
    # it for backward compat with pg<13 instances (R9 risk guard).
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # vector: pgvector extension — foundation for P02-S01-T001 embeddings.
    # Including here keeps §10.3 baseline atomic and makes the next migration
    # reversible (downgrade drops nothing the schema doesn't own — D5).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ------------------------------------------------------------------
    # 1. users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "preferred_language",
            sa.Text(),
            server_default="es",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "preferred_language IN ('es', 'en', 'fr')",
            name="ck_users_users_language_chk",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    # ------------------------------------------------------------------
    # 2. employee_profiles
    # ------------------------------------------------------------------
    op.create_table(
        "employee_profiles",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.Text(), nullable=False),
        sa.Column("brand", sa.Text(), nullable=False),
        sa.Column("society", sa.Text(), nullable=False),
        sa.Column("center", sa.Text(), nullable=False),
        sa.Column("country", sa.Text(), nullable=False),
        sa.Column("department", sa.Text(), nullable=False),
        sa.Column(
            "metadata",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_employee_profiles_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_employee_profiles"),
        sa.UniqueConstraint("employee_id", name="uq_employee_profiles_employee_id"),
    )

    # ------------------------------------------------------------------
    # 3. roles
    # ------------------------------------------------------------------
    op.create_table(
        "roles",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )

    # ------------------------------------------------------------------
    # 4. permissions
    # ------------------------------------------------------------------
    op.create_table(
        "permissions",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("key", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_permissions"),
        sa.UniqueConstraint("key", name="uq_permissions_key"),
    )

    # ------------------------------------------------------------------
    # 5. user_roles (M:N association)
    # ------------------------------------------------------------------
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_roles_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name="fk_user_roles_role_id_roles",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "role_id", name="pk_user_roles"),
    )

    # Explicit index for reverse join (role → users).
    # PG only auto-indexes the leading FK column in the PK; role_id lookup
    # needs a separate index (task-pack §7.2).
    op.create_index(
        "user_roles_role_id_idx",
        "user_roles",
        ["role_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # 6. refresh_tokens
    # ------------------------------------------------------------------
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_refresh_tokens_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_refresh_tokens"),
    )

    # Per-user enumeration index (task-pack §7.2).
    op.create_index(
        "refresh_tokens_user_id_idx",
        "refresh_tokens",
        ["user_id"],
        unique=False,
    )

    # Partial index for active tokens — efficient janitor sweep (task-pack §7.2).
    op.create_index(
        "refresh_tokens_active_expires_idx",
        "refresh_tokens",
        ["expires_at"],
        unique=False,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    # ------------------------------------------------------------------
    # 7. mfa_totp_secrets
    # ------------------------------------------------------------------
    op.create_table(
        "mfa_totp_secrets",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("secret_encrypted", sa.Text(), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_mfa_totp_secrets_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_mfa_totp_secrets"),
    )

    # ------------------------------------------------------------------
    # 8. password_reset_tokens
    # ------------------------------------------------------------------
    op.create_table(
        "password_reset_tokens",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_password_reset_tokens_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_password_reset_tokens"),
    )

    # Per-user lookup index.
    op.create_index(
        "password_reset_tokens_user_id_idx",
        "password_reset_tokens",
        ["user_id"],
        unique=False,
    )

    # Janitor sweep index for expired tokens.
    op.create_index(
        "password_reset_tokens_expires_idx",
        "password_reset_tokens",
        ["expires_at"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # 9. audit_logs
    # ------------------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=True),
        sa.Column("entity_id", sa.UUID(), nullable=True),
        sa.Column(
            "metadata",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_audit_logs_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
    )

    # Per-actor newest-first (§3.1 audit rule: "show me what user X did").
    op.create_index(
        "audit_logs_actor_created_idx",
        "audit_logs",
        ["actor_user_id", sa.text("created_at DESC")],
        unique=False,
    )

    # Global newest-first.
    op.create_index(
        "audit_logs_created_idx",
        "audit_logs",
        [sa.text("created_at DESC")],
        unique=False,
    )

    # Entity-type + entity-id lookup ("what happened to entity X").
    op.create_index(
        "audit_logs_entity_idx",
        "audit_logs",
        ["entity_type", "entity_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop all indexes and tables created by this migration (reverse order).

    Note: extensions pgcrypto and vector are NOT dropped — other tools or
    future migrations may rely on them, and CREATE EXTENSION IF NOT EXISTS
    is idempotent on re-upgrade.  Dropping extensions in downgrade would
    require a human decision (task-pack §7.3 decision).
    """

    # ------------------------------------------------------------------
    # Drop indexes first (before their tables)
    # ------------------------------------------------------------------
    # audit_logs indexes
    op.drop_index("audit_logs_entity_idx", table_name="audit_logs")
    op.drop_index("audit_logs_created_idx", table_name="audit_logs")
    op.drop_index("audit_logs_actor_created_idx", table_name="audit_logs")

    # password_reset_tokens indexes
    op.drop_index("password_reset_tokens_expires_idx", table_name="password_reset_tokens")
    op.drop_index("password_reset_tokens_user_id_idx", table_name="password_reset_tokens")

    # refresh_tokens indexes
    op.drop_index("refresh_tokens_active_expires_idx", table_name="refresh_tokens")
    op.drop_index("refresh_tokens_user_id_idx", table_name="refresh_tokens")

    # user_roles index
    op.drop_index("user_roles_role_id_idx", table_name="user_roles")

    # ------------------------------------------------------------------
    # Drop tables in reverse dependency order (children first)
    # ------------------------------------------------------------------
    op.drop_table("audit_logs")
    op.drop_table("password_reset_tokens")
    op.drop_table("mfa_totp_secrets")
    op.drop_table("refresh_tokens")
    op.drop_table("user_roles")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("employee_profiles")
    op.drop_table("users")
