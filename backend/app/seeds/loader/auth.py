"""
Loader for the 'auth' namespace.

Slice: P00-S02-T005 — Replace synthetic verification bundle with People Tech delivery
Phase: P00 — Scaffold + Design System

Loads mfa_primary.json + users/employee_primary.json + users/admin_peopletech.json
into the real §10.3 schema tables:
  - users (email, password_hash, full_name, status, preferred_language)
  - employee_profiles (user_id FK, employee_id, brand, society, center, country, department)
  - mfa_totp_secrets (user_id FK, secret_encrypted via Fernet, enabled)
  - roles (employee, admin — idempotent lookup rows)
  - user_roles (user_id, role_id — M:N association)

CHANGE from T003:
  - SQL rewritten to match real migration 0001 §10.3 column names.
  - password_hash computed via argon2.PasswordHasher (dep already pinned).
  - mfa_totp_secrets uses Fernet-encrypted secret (ENCRYPTION_KEY env var).
  - roles and user_roles seeded idempotently.
  - bundle_type propagated from MANIFEST via bootstrap; MfaPrimarySeed validated
    with validate_with_bundle_type() to enforce synthetic/productive invariants.

SECURITY:
  - password_plain_for_seed is NEVER logged (masked as '***' in log events).
  - totp_secret is NEVER logged; only the Fernet-encrypted form reaches the DB.
  - ENCRYPTION_KEY is NEVER logged; validated at startup.

DEFAULT employee_profile values (when JSON does not override):
  - employee_id: "EMP-{sha256(email)[:8].upper()}"
  - brand: "Hilo"
  - society: "Hilo People"
  - center: "HQ"
  - country: "ES"

Dependencies:
  - argon2-cffi 25.1.0 (PasswordHasher)
  - cryptography 48.0.0 (Fernet)
  - sqlalchemy[asyncio] 2.0.49
  - pydantic 2.12.5
  - structlog 25.5.0
"""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.logging import get_logger
from app.seeds.io import BundleLoadError, load_fixture
from app.seeds.loader._common import BundleType, LoadReport, _hash_email
from app.seeds.schemas.auth import MfaPrimarySeed
from app.seeds.schemas.users import UserSeed
from app.seeds.table_probe import table_exists

_logger = get_logger(__name__)

# Argon2id parameters — OWASP 2024 compliant defaults.
# argon2-cffi 25.1.0 defaults: m=65536 (64MB), t=3, p=4 — OWASP-2024 compliant.
_PH = PasswordHasher()


def _get_fernet() -> Fernet:
    """Return a Fernet cipher initialized from ENCRYPTION_KEY env var.

    Purpose: Fernet-encrypt TOTP secrets before writing to mfa_totp_secrets.
    Errors: BundleLoadError if ENCRYPTION_KEY is missing or invalid format.
    """
    key = os.environ.get("ENCRYPTION_KEY", "").strip()
    if not key:
        raise BundleLoadError(
            Path(".env"),
            "ENCRYPTION_KEY env var is required for MFA TOTP encryption. "
            "Set it in .env (see .env.example) before seeding with mfa_enabled=True users.",
        )
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise BundleLoadError(
            Path(".env"),
            "ENCRYPTION_KEY is not a valid Fernet key (32-byte URL-safe base64). "
            "Generate with: python3 -c "
            "'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'.",
        ) from exc


def _hash_employee_id(email: str) -> str:
    """Generate a default employee_id from email SHA-256 (first 8 chars, uppercase)."""
    return "EMP-" + hashlib.sha256(email.encode()).hexdigest()[:8].upper()


async def load_auth(
    engine: AsyncEngine,
    source_dir: Path,
    *,
    dry_run: bool = False,
    bundle_type: BundleType = "synthetic",
) -> LoadReport:
    """Load the 'auth' namespace: mfa_primary.json + users/*.json.

    Purpose: seed the primary employee and admin users for J100 auth journey.
    Tables targeted: users, employee_profiles, mfa_totp_secrets, roles, user_roles.
    Table-tolerant: logs WARN and skips if the table does not exist yet.

    Business rules:
      - Passwords hashed via argon2id (OWASP 2024 compliant).
      - TOTP secrets Fernet-encrypted before writing (requires ENCRYPTION_KEY).
      - Roles 'employee' and 'admin' created idempotently.
      - user_roles M:N association created per UserSeed.role.
      - preferred_language from employee_profile.language_preference or fallback 'es'.

    Params:
      engine      — async engine for DB access.
      source_dir  — verification bundle root directory.
      dry_run     — if True, validate only; do not write to DB.
      bundle_type — 'synthetic' or 'productive'; forwarded to MfaPrimarySeed validator.
    Returns: LoadReport with counts.
    Errors: BundleLoadError if a required fixture is missing, invalid, or env var missing.
    """
    t0 = time.monotonic()
    report = LoadReport(namespace="auth", dry_run=dry_run)
    ns = "auth"

    _logger.info(
        "seed.namespace.start",
        namespace=ns,
        dry_run=dry_run,
        bundle_type=bundle_type,
    )

    # Load + validate fixture files.
    employee: UserSeed = load_fixture(source_dir, "users", "employee_primary.json", UserSeed)
    admin: UserSeed = load_fixture(source_dir, "users", "admin_peopletech.json", UserSeed)
    mfa_raw = _load_mfa_raw(source_dir)
    mfa: MfaPrimarySeed = MfaPrimarySeed.validate_with_bundle_type(mfa_raw, bundle_type)

    if dry_run:
        _logger.info(
            "seed.namespace.done",
            namespace=ns,
            persisted=0,
            skipped_missing_table=0,
            dry_run=True,
        )
        report.duration_ms = (time.monotonic() - t0) * 1000
        return report

    # Check required tables.
    users_exist = await table_exists(engine, "users")
    if not users_exist:
        _logger.warning(
            "seed.namespace.table_missing",
            namespace=ns,
            table="users",
            reason="table_missing",
            action="skipped",
        )
        report.skipped_tables.append("users")
        report.duration_ms = (time.monotonic() - t0) * 1000
        _logger.info(
            "seed.namespace.done",
            namespace=ns,
            persisted=0,
            skipped_missing_table=1,
            duration_ms=round(report.duration_ms, 1),
        )
        return report

    # Seed roles idempotently (do this first — user_roles depend on it).
    await _seed_roles(engine, report)

    # Upsert both users.
    users_to_seed = [employee, admin]
    for user in users_to_seed:
        await _upsert_user(engine, user, report)

    # MFA — only for employee (mfa_enabled=True).
    mfa_exist = await table_exists(engine, "mfa_totp_secrets")
    if not mfa_exist:
        _logger.warning(
            "seed.namespace.table_missing",
            namespace=ns,
            table="mfa_totp_secrets",
            reason="table_missing",
            action="skipped",
        )
        report.skipped_tables.append("mfa_totp_secrets")
    else:
        if employee.mfa_enabled:
            await _upsert_mfa(engine, employee, mfa, report)

    report.duration_ms = (time.monotonic() - t0) * 1000
    _logger.info(
        "seed.namespace.done",
        namespace=ns,
        persisted=report.rows_inserted,
        skipped_missing_table=len(report.skipped_tables),
        duration_ms=round(report.duration_ms, 1),
    )
    return report


def _load_mfa_raw(source_dir: Path) -> dict:
    """Load mfa_primary.json as a raw dict (without Pydantic validation).

    Purpose: allow bundle_type injection before MfaPrimarySeed.validate_with_bundle_type().
    """
    import json
    mfa_path = source_dir / "auth" / "mfa_primary.json"
    if not mfa_path.exists():
        raise BundleLoadError(
            mfa_path,
            "Required fixture file not found. auth namespace requires 'mfa_primary.json'.",
        )
    raw = json.loads(mfa_path.read_text(encoding="utf-8"))
    # Strip _-prefixed keys (same as io.load_fixture).
    return {k: v for k, v in raw.items() if not k.startswith("_")}


async def _seed_roles(engine: AsyncEngine, report: LoadReport) -> None:
    """Upsert canonical roles ('employee', 'admin') idempotently.

    Purpose: ensure roles exist before user_roles can reference them.
    """
    roles_exist = await table_exists(engine, "roles")
    if not roles_exist:
        _logger.warning(
            "seed.namespace.table_missing",
            namespace="auth",
            table="roles",
            reason="table_missing",
            action="skipped",
        )
        report.skipped_tables.append("roles")
        return

    for role_name in ("employee", "admin"):
        _logger.debug("seed.auth.upsert_role.before", role_name=role_name)
        async with engine.begin() as conn:
            result = await conn.execute(
                text(
                    """
                    INSERT INTO roles (name)
                    VALUES (:name)
                    ON CONFLICT (name) DO NOTHING
                    """
                ),
                {"name": role_name},
            )
        rows = max(result.rowcount, 0)
        report.rows_inserted += rows
        _logger.debug("seed.auth.upsert_role.after", role_name=role_name, rows=rows)


async def _upsert_user(engine: AsyncEngine, user: UserSeed, report: LoadReport) -> None:
    """Upsert a single user row and its employee_profile and user_roles.

    Purpose: idempotent upsert for users, employee_profiles, user_roles tables.
    Logs BEFORE/AFTER without any PII (uses email hash).
    """
    email_hash = _hash_email(str(user.email))
    email = str(user.email)
    preferred_language = "es"
    if user.employee_profile:
        preferred_language = user.employee_profile.language_preference or "es"

    # Compute password hash (argon2id).
    pw_hash = _PH.hash(user.password_plain_for_seed)

    _logger.debug(
        "seed.auth.upsert_user.before",
        email_hash=email_hash,
        role=user.role,
        preferred_language=preferred_language,
    )

    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                INSERT INTO users (email, password_hash, full_name, status, preferred_language)
                VALUES (:email, :password_hash, :full_name, 'active', :preferred_language)
                ON CONFLICT (email) DO UPDATE SET
                  password_hash = EXCLUDED.password_hash,
                  full_name = EXCLUDED.full_name,
                  status = EXCLUDED.status,
                  preferred_language = EXCLUDED.preferred_language,
                  updated_at = NOW()
                RETURNING id
                """
            ),
            {
                "email": email,
                "password_hash": pw_hash,
                "full_name": user.full_name,
                "preferred_language": preferred_language,
            },
        )
        user_row = result.fetchone()
        user_id = user_row[0] if user_row else None

    if user_id is None:
        # If ON CONFLICT DO UPDATE did not RETURN (upserted on conflict without RETURNING
        # from INSERT path), we fetch the id separately.
        async with engine.begin() as conn:
            result = await conn.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": email},
            )
            user_id = result.scalar_one()

    report.rows_inserted += 1
    _logger.debug("seed.auth.upsert_user.after", email_hash=email_hash, user_id_present=True)

    # employee_profiles (only for role=employee with profile data).
    if user.employee_profile:
        ep = user.employee_profile
        emp_id = _hash_employee_id(email)
        _logger.debug("seed.auth.upsert_employee_profile.before", email_hash=email_hash)
        async with engine.begin() as conn:
            ep_exist = await table_exists(engine, "employee_profiles")
            if ep_exist:
                await conn.execute(
                    text(
                        """
                        INSERT INTO employee_profiles
                          (user_id, employee_id, brand, society, center, country, department)
                        VALUES
                          (:user_id, :employee_id, :brand, :society, :center, :country, :department)
                        ON CONFLICT (user_id) DO UPDATE SET
                          employee_id = EXCLUDED.employee_id,
                          brand = EXCLUDED.brand,
                          society = EXCLUDED.society,
                          center = EXCLUDED.center,
                          country = EXCLUDED.country,
                          department = EXCLUDED.department
                        """
                    ),
                    {
                        "user_id": str(user_id),
                        "employee_id": emp_id,
                        "brand": "Hilo",
                        "society": "Hilo People",
                        "center": "HQ",
                        "country": "ES",
                        "department": ep.department,
                    },
                )
                report.rows_inserted += 1
                _logger.debug(
                    "seed.auth.upsert_employee_profile.after",
                    email_hash=email_hash,
                    employee_id=emp_id,
                )

    # user_roles.
    roles_exist = await table_exists(engine, "roles")
    user_roles_exist = await table_exists(engine, "user_roles")
    if roles_exist and user_roles_exist:
        _logger.debug("seed.auth.upsert_user_role.before", email_hash=email_hash, role=user.role)
        async with engine.begin() as conn:
            role_result = await conn.execute(
                text("SELECT id FROM roles WHERE name = :name"),
                {"name": user.role},
            )
            role_row = role_result.fetchone()
            if role_row:
                role_id = role_row[0]
                await conn.execute(
                    text(
                        """
                        INSERT INTO user_roles (user_id, role_id)
                        VALUES (:user_id, :role_id)
                        ON CONFLICT (user_id, role_id) DO NOTHING
                        """
                    ),
                    {"user_id": str(user_id), "role_id": str(role_id)},
                )
                report.rows_inserted += 1
        _logger.debug("seed.auth.upsert_user_role.after", email_hash=email_hash, role=user.role)


async def _upsert_mfa(
    engine: AsyncEngine,
    user: UserSeed,
    mfa: MfaPrimarySeed,
    report: LoadReport,
) -> None:
    """Upsert mfa_totp_secrets for a user with mfa_enabled=True.

    Purpose: Fernet-encrypt the TOTP secret before writing to DB.
    The plaintext secret is NEVER logged or stored unencrypted.
    Errors: BundleLoadError if ENCRYPTION_KEY is missing or invalid.
    """
    email_hash = _hash_email(str(user.email))
    _logger.debug("seed.auth.upsert_mfa.before", email_hash=email_hash)

    fernet = _get_fernet()
    secret_encrypted = fernet.encrypt(mfa.totp_secret.encode()).decode()

    async with engine.begin() as conn:
        # Lookup user_id by email.
        uid_result = await conn.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": str(user.email)},
        )
        user_id = uid_result.scalar_one_or_none()

    if user_id is None:
        _logger.warning(
            "seed.auth.upsert_mfa.user_not_found",
            email_hash=email_hash,
            action="skipped",
        )
        return

    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO mfa_totp_secrets (user_id, secret_encrypted, enabled)
                VALUES (:user_id, :secret_encrypted, :enabled)
                ON CONFLICT (user_id) DO UPDATE SET
                  secret_encrypted = EXCLUDED.secret_encrypted,
                  enabled = EXCLUDED.enabled
                """
            ),
            {
                "user_id": str(user_id),
                "secret_encrypted": secret_encrypted,
                "enabled": True,
            },
        )

    report.rows_inserted += 1
    _logger.debug("seed.auth.upsert_mfa.after", email_hash=email_hash, encrypted=True)
