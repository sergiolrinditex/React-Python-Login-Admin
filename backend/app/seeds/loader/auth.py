"""
Loader for the 'auth' namespace.

Slice: P00-S02-T003 — Seed data and reset verification bundle
Phase: P00 — Scaffold + Design System

Loads mfa_primary.json + users/employee_primary.json into users +
user_mfa_configs (table-tolerant).

Dependencies:
  - sqlalchemy[asyncio] 2.0.49
  - pydantic 2.12.5
  - structlog 25.5.0
"""
from __future__ import annotations

import time
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.logging import get_logger
from app.seeds.io import load_fixture
from app.seeds.loader._common import LoadReport, _hash_email
from app.seeds.schemas.auth import MfaPrimarySeed
from app.seeds.schemas.users import UserSeed
from app.seeds.table_probe import table_exists

_logger = get_logger(__name__)


async def load_auth(
    engine: AsyncEngine,
    source_dir: Path,
    *,
    dry_run: bool = False,
) -> LoadReport:
    """Load the 'auth' namespace: mfa_primary.json + users/*.json.

    Purpose: seed the primary employee user and MFA config for J100 auth journey.
    Tables targeted: users, employee_profiles, user_mfa_configs.
    Table-tolerant: logs WARN and skips if the table does not exist yet.

    Params:
      engine     — async engine for DB access.
      source_dir — verification bundle root directory.
      dry_run    — if True, validate only; do not write to DB.
    Returns: LoadReport with counts.
    Errors: BundleLoadError if a required fixture is missing or invalid.
    """
    t0 = time.monotonic()
    report = LoadReport(namespace="auth", dry_run=dry_run)
    ns = "auth"

    _logger.info(
        "seed.namespace.start",
        namespace=ns,
        dry_run=dry_run,
    )

    # Load + validate both fixture files.
    employee = load_fixture(source_dir, "users", "employee_primary.json", UserSeed)
    mfa = load_fixture(source_dir, ns, "mfa_primary.json", MfaPrimarySeed)

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
    else:
        # Upsert user row idempotently by email (natural key).
        email_hash = _hash_email(str(employee.email))
        _logger.debug("seed.auth.upsert_user.before", email_hash=email_hash)
        async with engine.begin() as conn:
            result = await conn.execute(
                text(
                    """
                    INSERT INTO users (email, full_name, role, is_active, mfa_enabled)
                    VALUES (:email, :full_name, :role, :is_active, :mfa_enabled)
                    ON CONFLICT (email) DO UPDATE
                      SET full_name = EXCLUDED.full_name,
                          role = EXCLUDED.role,
                          is_active = EXCLUDED.is_active,
                          mfa_enabled = EXCLUDED.mfa_enabled
                    """
                ),
                {
                    "email": str(employee.email),
                    "full_name": employee.full_name,
                    "role": employee.role,
                    "is_active": employee.is_active,
                    "mfa_enabled": employee.mfa_enabled,
                },
            )
        rows = result.rowcount if result.rowcount >= 0 else 1
        report.rows_inserted += rows
        _logger.debug("seed.auth.upsert_user.after", email_hash=email_hash, rows=rows)

    # MFA config table (optional — lands in P01-S02-T001).
    mfa_exist = await table_exists(engine, "user_mfa_configs")
    if not mfa_exist:
        _logger.warning(
            "seed.namespace.table_missing",
            namespace=ns,
            table="user_mfa_configs",
            reason="table_missing",
            action="skipped",
        )
        report.skipped_tables.append("user_mfa_configs")
    else:
        # MFA config upsert would go here (using email FK lookup).
        # Table not yet defined — left as no-op placeholder.
        _logger.debug("seed.auth.mfa_table_exists_but_no_schema", totp_algo=mfa.algorithm)

    report.duration_ms = (time.monotonic() - t0) * 1000
    _logger.info(
        "seed.namespace.done",
        namespace=ns,
        persisted=report.rows_inserted,
        skipped_missing_table=len(report.skipped_tables),
        duration_ms=round(report.duration_ms, 1),
    )
    return report
