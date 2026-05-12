"""
Hilo People — Verification data bootstrap entry point.

Slice:  P00-S02-T003 — Verification data loader and reset
Phase:  P00 Scaffold + Design System
Purpose: CLI entry point invoked as `python -m app.verification_data.bootstrap`.
         Reads JSON fixtures from data/verification/, validates with Pydantic v2,
         and loads them into Postgres idempotently (UPSERT / deferred if tables
         absent). Follows the exact command contract from §15 instrucciones and
         §6.5 TECHNICAL_GUIDE.

         Exit codes:
           0 — success (all groups OK or deferred; fixture validation passed)
           1 — data/verification/ directory not found or missing required files
           2 — Pydantic ValidationError (invalid fixture schema)
           3 — unexpected runtime error (DB connection, filesystem, etc.)

Key deps:
  - argparse (stdlib)
  - pydantic==2.12.5 (fixture validation)
  - sqlalchemy==2.0.49 (sync engine + session)
  - structlog==25.5.0 (structured logging)
  - app.verification_data.loader (group loaders)
  - app.verification_data.groups (VALID_GROUPS)
  - DATABASE_URL env var (postgresql+psycopg://...)

Invocation:
  python -m app.verification_data.bootstrap --source data/verification
  python -m app.verification_data.bootstrap --source data/verification --only auth
  python -m app.verification_data.bootstrap --source data/verification --dry-run

Source refs:
  - docs/source-of-truth/instrucciones.md §15 Verification Data
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §6.5
  - docs/source-of-truth/STACK_PROFILE.yaml db.seed_cmd
  - 01-non-negotiables.md §Logging, §Security, §Database
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import structlog
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.verification_data.groups import VALID_GROUPS
from app.verification_data.loader import (
    LoadResult,
    load_admin_users,
    load_agents,
    load_ai_providers,
    load_mcp_servers,
    load_rag_collections,
    load_users,
)
from app.verification_data.schemas import (
    AdminUserFixture,
    AgentFixture,
    AiProviderFixture,
    ConversationFixture,
    EmployeeUserFixture,
    McpServerFixture,
    MfaSecretFixture,
    RagCollectionFixture,
    DocumentFixture,
)

# ---------------------------------------------------------------------------
# Logging configuration
# ENABLE_VERBOSE_LOGGING controls INFO vs WARNING+ERROR.
# Per 01-non-negotiables.md §Logging.
# ---------------------------------------------------------------------------
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"
_LOG_LEVEL: int = logging.INFO if _VERBOSE else logging.WARNING
logging.basicConfig(
    level=_LOG_LEVEL,
    format="%(asctime)s %(name)-30s %(levelname)-5s %(message)s",
    stream=sys.stderr,
)
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(_LOG_LEVEL),
)
log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Fixture reading helpers
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> dict[str, Any]:
    """Read and parse a JSON file.

    Args:
        path: Absolute or relative path to a .json file.

    Returns:
        Parsed dict.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If JSON is malformed.
    """
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_fixtures_from_dir(
    source_dir: Path,
    group: str,
    subpath: str,
) -> list[dict[str, Any]]:
    """Load all JSON fixtures from source_dir/group/subpath/*.json.

    Returns an empty list if the directory does not exist.

    Args:
        source_dir: Root verification data directory.
        group:      Group name (e.g. 'auth').
        subpath:    Sub-directory within the group (e.g. 'users').

    Returns:
        List of parsed fixture dicts (may be empty).
    """
    target = source_dir / group / subpath
    if not target.exists():
        return []
    results = []
    for json_file in sorted(target.glob("*.json")):
        results.append(_read_json(json_file))
    return results


def _load_mfa_secret(session: Any, fixture: "MfaSecretFixture") -> None:
    """Insert or UPSERT mfa_totp_secrets row for the verification user.

    Called only when mfa_primary.json.enabled=True and the DB tables exist.
    Encrypts the plaintext TOTP seed with Fernet(MFA_ENCRYPTION_KEY) before storage.
    Missing or invalid MFA_ENCRYPTION_KEY → warning only (loader continues).

    Args:
        session: Active SQLAlchemy Session (committed by caller).
        fixture: Validated MfaSecretFixture from auth/mfa_primary.json.

    Ref: task pack P01-S02-T006 §H Option A (WRITE_SET_DRIFT §D-MFA1.K).
    """
    import os
    from sqlalchemy import text

    enc_key = os.getenv("MFA_ENCRYPTION_KEY", "")
    if not enc_key:
        log.warning(
            "verification_data.mfa.skip",
            reason="MFA_ENCRYPTION_KEY not set; skipping MFA secret insert",
        )
        return
    try:
        from cryptography.fernet import Fernet
        Fernet(enc_key.encode())  # validate key
    except Exception as exc:
        log.warning(
            "verification_data.mfa.skip",
            reason=f"MFA_ENCRYPTION_KEY invalid: {exc}",
        )
        return

    from cryptography.fernet import Fernet
    encrypted = Fernet(enc_key.encode()).encrypt(fixture.totp_secret.encode()).decode()

    # Look up user by email ref
    result = session.execute(
        text("SELECT id FROM users WHERE email = :email"),
        {"email": str(fixture.user_email_ref)},
    ).first()
    if result is None:
        log.warning(
            "verification_data.mfa.skip",
            reason=f"user not found for email ref {fixture.user_email_ref.split('@')[0]}@...",
        )
        return

    user_id = result[0]
    session.execute(
        text(
            "INSERT INTO mfa_totp_secrets (user_id, secret_encrypted, enabled) "
            "VALUES (:uid, :enc, :enabled) "
            "ON CONFLICT (user_id) DO UPDATE SET "
            "  secret_encrypted = EXCLUDED.secret_encrypted, "
            "  enabled = EXCLUDED.enabled"
        ),
        {"uid": str(user_id), "enc": encrypted, "enabled": True},
    )
    session.commit()
    log.info(
        "verification_data.mfa.loaded",
        email_domain=str(fixture.user_email_ref).split("@")[-1],
        enabled=True,
    )


# ---------------------------------------------------------------------------
# Group loader dispatchers
# ---------------------------------------------------------------------------

def _run_auth_group(source_dir: Path, session: Any, engine: Any, dry_run: bool) -> list[LoadResult]:
    """Load auth group: employee users + employee profiles + MFA secrets.

    Args:
        source_dir: Root verification data directory.
        session:    SQLAlchemy sync Session.
        engine:     SQLAlchemy Engine.
        dry_run:    If True, validate fixtures but do not touch DB.

    Returns:
        List of LoadResult for each sub-loader executed.
    """
    results: list[LoadResult] = []
    if _VERBOSE:
        log.info("verification_data.group.auth.start")

    raw_employees = _load_fixtures_from_dir(source_dir, "users", "")
    if not raw_employees:
        raw_employees = [_read_json(source_dir / "users" / "employee_primary.json")] \
            if (source_dir / "users" / "employee_primary.json").exists() else []

    employee_fixtures = []
    for raw in raw_employees:
        if "employee_profile" in raw:  # only employee users
            fx = EmployeeUserFixture.model_validate(raw)
            employee_fixtures.append(fx)

    # Load and validate MFA fixture (P01-S02-T006 WRITE_SET_DRIFT §D-MFA1.K).
    mfa_fixture: MfaSecretFixture | None = None
    mfa_path = source_dir / "auth" / "mfa_primary.json"
    if mfa_path.exists():
        mfa_raw = _read_json(mfa_path)
        mfa_fixture = MfaSecretFixture.model_validate(mfa_raw)

    if dry_run:
        if _VERBOSE:
            log.info("verification_data.group.auth.dry_run", employee_count=len(employee_fixtures))
        results.append(LoadResult(group="auth", status="dry_run", reason="--dry-run flag"))
        return results

    if employee_fixtures:
        res = load_users(session, engine, employee_fixtures, group_name="auth")
        results.append(res)
    else:
        results.append(LoadResult(group="auth", status="ok", reason="no employee fixtures found"))

    # Insert MFA TOTP secret for verification user if fixture declares enabled=True.
    # Requires MFA_ENCRYPTION_KEY env var. Missing key → warning + skip (non-fatal).
    if mfa_fixture and mfa_fixture.enabled:
        _load_mfa_secret(session, mfa_fixture)

    if _VERBOSE:
        log.info("verification_data.group.auth.done")
    return results


def _run_history_group(source_dir: Path, session: Any, engine: Any, dry_run: bool) -> list[LoadResult]:
    """Load history group: user + conversation data for J102.

    Args:
        source_dir: Root verification data directory.
        session:    SQLAlchemy sync Session.
        engine:     SQLAlchemy Engine.
        dry_run:    If True, validate fixtures but do not touch DB.

    Returns:
        List of LoadResult for each sub-loader.
    """
    if _VERBOSE:
        log.info("verification_data.group.history.start")

    raw_employees = []
    emp_path = source_dir / "users" / "employee_primary.json"
    if emp_path.exists():
        raw_employees = [_read_json(emp_path)]

    employee_fixtures = [
        EmployeeUserFixture.model_validate(r) for r in raw_employees if "employee_profile" in r
    ]

    # Validate conversations fixture.
    conv_path = source_dir / "history" / "conversations.json"
    if conv_path.exists():
        conv_raw = _read_json(conv_path)
        if isinstance(conv_raw, list):
            for item in conv_raw:
                ConversationFixture.model_validate(item)
        elif isinstance(conv_raw, dict):
            ConversationFixture.model_validate(conv_raw)

    if dry_run:
        if _VERBOSE:
            log.info("verification_data.group.history.dry_run")
        return [LoadResult(group="history", status="dry_run", reason="--dry-run flag")]

    if employee_fixtures:
        res = load_users(session, engine, employee_fixtures, group_name="history")
        return [res]

    return [LoadResult(group="history", status="ok", reason="no history fixtures found")]


def _run_admin_ai_group(source_dir: Path, session: Any, engine: Any, dry_run: bool) -> list[LoadResult]:
    """Load admin_ai group: admin users + AI providers.

    Args:
        source_dir: Root verification data directory.
        session:    SQLAlchemy sync Session.
        engine:     SQLAlchemy Engine.
        dry_run:    If True, validate fixtures but do not touch DB.

    Returns:
        List of LoadResult for each sub-loader.
    """
    if _VERBOSE:
        log.info("verification_data.group.admin_ai.start")

    admin_raw = []
    admin_path = source_dir / "users" / "admin_peopletech.json"
    if admin_path.exists():
        admin_raw = [_read_json(admin_path)]

    admin_fixtures = [AdminUserFixture.model_validate(r) for r in admin_raw]

    provider_raws = _load_fixtures_from_dir(source_dir, "admin_ai", "providers")
    provider_fixtures = [AiProviderFixture.model_validate(r) for r in provider_raws]

    if dry_run:
        if _VERBOSE:
            log.info("verification_data.group.admin_ai.dry_run")
        return [LoadResult(group="admin_ai", status="dry_run", reason="--dry-run flag")]

    results: list[LoadResult] = []
    if admin_fixtures:
        results.append(load_admin_users(session, engine, admin_fixtures))
    if provider_fixtures:
        results.append(load_ai_providers(session, engine, provider_fixtures))

    if not results:
        results.append(LoadResult(group="admin_ai", status="ok", reason="no admin_ai fixtures found"))
    return results


def _run_rag_chat_group(source_dir: Path, session: Any, engine: Any, dry_run: bool) -> list[LoadResult]:
    """Load rag_chat group: RAG collections + documents.

    Args:
        source_dir: Root verification data directory.
        session:    SQLAlchemy sync Session.
        engine:     SQLAlchemy Engine.
        dry_run:    If True, validate fixtures but do not touch DB.

    Returns:
        List of LoadResult for each sub-loader.
    """
    if _VERBOSE:
        log.info("verification_data.group.rag_chat.start")

    coll_raws = _load_fixtures_from_dir(source_dir, "rag_chat", "collections")
    coll_fixtures = [RagCollectionFixture.model_validate(r) for r in coll_raws]

    doc_raws = _load_fixtures_from_dir(source_dir, "rag_chat", "documents")
    # Validate documents even if we don't load them yet (table deferred)
    for _doc_raw in doc_raws:
        DocumentFixture.model_validate(_doc_raw)

    if dry_run:
        if _VERBOSE:
            log.info("verification_data.group.rag_chat.dry_run")
        return [LoadResult(group="rag_chat", status="dry_run", reason="--dry-run flag")]

    results: list[LoadResult] = []
    if coll_fixtures:
        results.append(load_rag_collections(session, engine, coll_fixtures, group_name="rag_chat"))
    if not results:
        results.append(LoadResult(group="rag_chat", status="ok", reason="no rag_chat fixtures found"))
    return results


def _run_rag_docs_group(source_dir: Path, session: Any, engine: Any, dry_run: bool) -> list[LoadResult]:
    """Load rag_docs group: RAG document metadata.

    Args:
        source_dir: Root verification data directory.
        session:    SQLAlchemy sync Session.
        engine:     SQLAlchemy Engine.
        dry_run:    If True, validate fixtures but do not touch DB.

    Returns:
        List of LoadResult for each sub-loader.
    """
    if _VERBOSE:
        log.info("verification_data.group.rag_docs.start")

    doc_raws = _load_fixtures_from_dir(source_dir, "rag_docs", "documents")
    doc_fixtures = [DocumentFixture.model_validate(r) for r in doc_raws]

    if dry_run:
        if _VERBOSE:
            log.info("verification_data.group.rag_docs.dry_run")
        return [LoadResult(group="rag_docs", status="dry_run", reason="--dry-run flag")]

    if not doc_fixtures:
        return [LoadResult(group="rag_docs", status="ok", reason="no rag_docs fixtures found")]
    # Documents depend on rag_collections; if that table is missing return deferred.
    from app.verification_data.loader import _table_exists
    if not _table_exists(engine, "documents"):
        log.warning(
            "verification_data.rag_docs.deferred_until_schema_ready",
            reason="table_missing", table="documents",
        )
        return [LoadResult(group="rag_docs", status="deferred", reason="table_missing:documents")]
    return [LoadResult(group="rag_docs", status="ok", reason="documents deferred (no load impl yet)")]


def _run_mcp_agents_group(source_dir: Path, session: Any, engine: Any, dry_run: bool) -> list[LoadResult]:
    """Load mcp_agents group: MCP servers + agents.

    Args:
        source_dir: Root verification data directory.
        session:    SQLAlchemy sync Session.
        engine:     SQLAlchemy Engine.
        dry_run:    If True, validate fixtures but do not touch DB.

    Returns:
        List of LoadResult for each sub-loader.
    """
    if _VERBOSE:
        log.info("verification_data.group.mcp_agents.start")

    server_raws = _load_fixtures_from_dir(source_dir, "mcp_agents", "servers")
    server_fixtures = [McpServerFixture.model_validate(r) for r in server_raws]

    agent_raws = _load_fixtures_from_dir(source_dir, "mcp_agents", "agents")
    agent_fixtures = [AgentFixture.model_validate(r) for r in agent_raws]

    if dry_run:
        if _VERBOSE:
            log.info("verification_data.group.mcp_agents.dry_run")
        return [LoadResult(group="mcp_agents", status="dry_run", reason="--dry-run flag")]

    results: list[LoadResult] = []
    if server_fixtures:
        results.append(load_mcp_servers(session, engine, server_fixtures))
    if agent_fixtures:
        results.append(load_agents(session, engine, agent_fixtures))
    if not results:
        results.append(LoadResult(group="mcp_agents", status="ok", reason="no mcp_agents fixtures found"))
    return results


# ---------------------------------------------------------------------------
# Group dispatcher map
# ---------------------------------------------------------------------------
_GROUP_RUNNERS = {
    "auth": _run_auth_group,
    "history": _run_history_group,
    "admin_ai": _run_admin_ai_group,
    "rag_chat": _run_rag_chat_group,
    "rag_docs": _run_rag_docs_group,
    "mcp_agents": _run_mcp_agents_group,
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Bootstrap entry point — parse args and run selected group loaders.

    Args:
        argv: CLI arguments (defaults to sys.argv[1:] if None).

    Returns:
        Exit code:
          0 — success (all groups OK or deferred)
          1 — source directory missing or required file not found
          2 — Pydantic ValidationError
          3 — unexpected runtime error
    """
    parser = argparse.ArgumentParser(
        prog="python -m app.verification_data.bootstrap",
        description="Load Hilo People verification fixtures into Postgres idempotently.",
    )
    parser.add_argument(
        "--source",
        default="data/verification",
        help="Path to verification data directory (default: data/verification)",
    )
    parser.add_argument(
        "--only",
        choices=list(VALID_GROUPS),
        metavar="GROUP",
        help=f"Load only this group. Valid choices: {', '.join(VALID_GROUPS)}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Validate fixtures without writing to DB.",
    )

    args = parser.parse_args(argv)

    source_dir = Path(args.source)
    log.info("verification_data.bootstrap.start", source=str(source_dir), only=args.only, dry_run=args.dry_run)

    # -- AC2: validate source directory exists.
    if not source_dir.exists() or not source_dir.is_dir():
        print(
            f"ERROR: verification data directory not found: {source_dir.resolve()}\n"
            "Set --source to the correct path. Expected: data/verification/",
            file=sys.stderr,
        )
        log.error("verification_data.bootstrap.error", reason="source_dir_not_found", path=str(source_dir))
        return 1

    # -- Determine groups to run.
    groups_to_run = [args.only] if args.only else list(VALID_GROUPS)

    # -- Create engine + session (skip if dry-run to avoid needing DB).
    engine = None
    session = None
    if not args.dry_run:
        db_url = os.getenv("DATABASE_URL", "")
        if not db_url:
            print(
                "ERROR: DATABASE_URL environment variable is not set.\n"
                "Set it to postgresql+psycopg://user:pass@host:port/db",
                file=sys.stderr,
            )
            log.error("verification_data.bootstrap.error", reason="DATABASE_URL_missing")
            return 3
        # Normalise asyncpg → psycopg for sync usage.
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
        try:
            engine = create_engine(db_url, pool_pre_ping=True)
            SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
            session = SessionLocal()
        except Exception as exc:
            print(f"ERROR: Could not connect to database: {exc}", file=sys.stderr)
            log.error("verification_data.bootstrap.error", reason="db_connect_failed", error=str(exc))
            return 3

    # -- Run groups and collect results.
    all_results: list[LoadResult] = []
    try:
        for group in groups_to_run:
            runner = _GROUP_RUNNERS[group]
            try:
                log.info(f"verification_data.group.{group}.start") if _VERBOSE else None
                group_results = runner(source_dir, session, engine, args.dry_run)
                all_results.extend(group_results)
            except ValidationError as exc:
                print(
                    f"ERROR: fixture validation failed for group '{group}':\n{exc}",
                    file=sys.stderr,
                )
                log.error("verification_data.bootstrap.validation_error", group=group, error=str(exc))
                return 2
            except Exception as exc:
                print(f"ERROR: unexpected error in group '{group}': {exc}", file=sys.stderr)
                log.error("verification_data.bootstrap.error", group=group, error=str(exc))
                return 3

    finally:
        if session is not None:
            session.close()
        if engine is not None:
            engine.dispose()

    # -- Summary output (stdout, grep-friendly JSON per line).
    summary = {
        "status": "ok",
        "groups": [
            {
                "group": r.group,
                "status": r.status,
                "inserted": r.inserted,
                "updated": r.updated,
                "skipped": r.skipped,
                "reason": r.reason,
            }
            for r in all_results
        ],
    }
    print(json.dumps(summary))
    log.info("verification_data.bootstrap.done", groups_run=len(groups_to_run))
    return 0


if __name__ == "__main__":
    sys.exit(main())
