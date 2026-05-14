"""
Hilo People — Verification data loader (core UPSERT logic).

Slice:  P00-S02-T003 — Verification data loader and reset
        P02-S03-T004 — Added load_ai_provider_credentials() + load_ai_models()
Phase:  P00 Scaffold + Design System / P02 Core Features
Purpose: Contains one load_<group> function per fixture category. Each function:
           1. Inspects the Postgres schema at runtime to check if the target
              table exists (sqlalchemy.inspect().has_table()). If not → returns
              a deferred LoadResult (WARN, exit-code 0).
           2. If the table exists → performs idempotent UPSERT using
              INSERT ... ON CONFLICT DO UPDATE via SQLAlchemy dialects.postgresql.

         Password idempotency pattern (non-trivial, per §N.1):
           - Argon2 produces a different hash each time (random salt).
           - INSERT branch: always hash and insert.
           - UPDATE branch: verify existing stored_hash against plain.
             If verify OK → keep existing hash (no re-hash). If verify FAILS
             (plain changed) → re-hash and update. This ensures AC1 passes.

         P02-S03-T004 additions:
           - load_ai_provider_credentials(): encrypts credential_plain at LOAD TIME
             via app.security.encryption.encrypt_secret() (Fernet AEAD). The plain
             credential is NEVER stored in the DB. Idempotency key: (provider_id, auth_type).
           - load_ai_models(): upserts ai_models rows. Idempotency key: (provider_id, model_id).
             Both functions use _table_exists() deferred-skip pattern.

Key deps:
  - sqlalchemy==2.0.49 (create_engine, inspect, dialects.postgresql.insert)
  - argon2-cffi==25.1.0 (via crypto.py)
  - cryptography==48.0.0 (via app.security.encryption — for load_ai_provider_credentials)
  - structlog==25.5.0 (structured BEFORE/AFTER/ERROR logging)

Source refs:
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §6.5, §10.3
  - 01-non-negotiables.md §Logging, §Security, §Database
  - 01-non-negotiables.md §Tests are REAL — hits real Postgres, no SQLite.
  - P02-S03-T004 D-T004-A4 (loader split SRP), D-T004-A5 (FK-safe order),
    D-T004-A6 (encrypt at load time)
"""

import json

import structlog
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.verification_data.crypto import hash_password, verify_password
from app.verification_data.loader_base import LoadResult, _info, _table_exists  # noqa: F401
from app.verification_data.loader_ai_tables import (  # noqa: F401
    load_ai_models,
    load_ai_provider_credentials,
)
from app.verification_data.redaction import mask_email
from app.verification_data.schemas import (
    AdminUserFixture,
    AgentFixture,
    AiProviderFixture,
    EmployeeUserFixture,
    McpServerFixture,
    RagCollectionFixture,
)

# ---------------------------------------------------------------------------
# Logger — structlog; falls back to stdlib if structlog not configured yet.
# ---------------------------------------------------------------------------
log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Shared helper — upsert a single user row
# ---------------------------------------------------------------------------
def _upsert_user(
    session: Session,
    engine: Engine,
    email: str,
    full_name: str,
    password_plain: str,
    status: str,
    preferred_language: str,
) -> tuple[str, int, int, int]:
    """Insert or update a user row. Returns (action, inserted, updated, skipped).

    Idempotency: if the user exists and the password verifies OK, skip
    re-hashing. If the password changed, re-hash and update.

    Args:
        session:           SQLAlchemy Session (sync).
        engine:            Engine for metadata inspection.
        email:             Unique user email.
        full_name:         Display name.
        password_plain:    Plain-text password from fixture.
        status:            User account status.
        preferred_language: ISO-639-1 language code.

    Returns:
        Tuple of (action_str, inserted_count, updated_count, skipped_count).
    """
    # Check if user exists already.
    existing = session.execute(
        text("SELECT id, password_hash FROM users WHERE email = :email"),
        {"email": email},
    ).fetchone()

    if existing is None:
        # INSERT branch — hash fresh.
        hashed = hash_password(password_plain)
        session.execute(
            text(
                "INSERT INTO users (email, full_name, password_hash, status, preferred_language)"
                " VALUES (:email, :full_name, :pw_hash, :status, :lang)"
            ),
            {
                "email": email,
                "full_name": full_name,
                "pw_hash": hashed,
                "status": status,
                "lang": preferred_language,
            },
        )
        return "inserted", 1, 0, 0
    else:
        # UPDATE branch — verify existing hash first.
        stored_hash: str = existing[1]
        pw_ok = verify_password(password_plain, stored_hash)
        if pw_ok:
            # Hash verifies — no need to re-hash; update non-secret fields only.
            session.execute(
                text(
                    "UPDATE users SET full_name = :full_name, status = :status,"
                    " preferred_language = :lang"
                    " WHERE email = :email"
                ),
                {
                    "full_name": full_name,
                    "status": status,
                    "lang": preferred_language,
                    "email": email,
                },
            )
            return "skipped_hash", 0, 1, 0
        else:
            # Password changed — re-hash and update.
            hashed = hash_password(password_plain)
            session.execute(
                text(
                    "UPDATE users SET full_name = :full_name, status = :status,"
                    " preferred_language = :lang, password_hash = :pw_hash"
                    " WHERE email = :email"
                ),
                {
                    "full_name": full_name,
                    "status": status,
                    "lang": preferred_language,
                    "pw_hash": hashed,
                    "email": email,
                },
            )
            return "updated_hash", 0, 1, 0


# ---------------------------------------------------------------------------
# Group loaders
# ---------------------------------------------------------------------------

def load_users(
    session: Session,
    engine: Engine,
    fixtures: list[EmployeeUserFixture],
    group_name: str = "auth",
) -> LoadResult:
    """Load employee users + profiles idempotently into Postgres.

    Checks at runtime that 'users' and 'employee_profiles' tables exist.
    If not, returns deferred LoadResult without touching DB.

    Args:
        session:    Active SQLAlchemy sync Session.
        engine:     Engine for table-existence checks.
        fixtures:   List of validated EmployeeUserFixture objects.
        group_name: Log label (e.g. 'auth', 'history').

    Returns:
        LoadResult with counts and status.
    """
    _info(
        f"verification_data.{group_name}.users.start",
        count=len(fixtures),
    )
    log.debug(f"verification_data.{group_name}.users.start", count=len(fixtures))

    if not _table_exists(engine, "users"):
        log.warning(
            f"verification_data.{group_name}.deferred_until_schema_ready",
            reason="table_missing",
            table="users",
        )
        return LoadResult(group=group_name, status="deferred", reason="table_missing:users")

    total_inserted = total_updated = total_skipped = 0

    for fx in fixtures:
        safe_email = mask_email(str(fx.email))
        _info(
            f"verification_data.{group_name}.users.upsert",
            email=safe_email,
            status=fx.status,
        )
        action, ins, upd, skp = _upsert_user(
            session,
            engine,
            str(fx.email),
            fx.full_name,
            fx.password_plain,
            fx.status,
            fx.preferred_language,
        )
        total_inserted += ins
        total_updated += upd
        total_skipped += skp

        # Load employee_profile if table exists.
        if _table_exists(engine, "employee_profiles"):
            user_row = session.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": str(fx.email)},
            ).fetchone()
            if user_row:
                user_id = str(user_row[0])
                ep = fx.employee_profile
                existing_ep = session.execute(
                    text("SELECT user_id FROM employee_profiles WHERE user_id = :uid"),
                    {"uid": user_id},
                ).fetchone()
                if existing_ep is None:
                    session.execute(
                        text(
                            "INSERT INTO employee_profiles"
                            " (user_id, employee_id, brand, society, center, country, department, metadata)"
                            " VALUES (:uid, :eid, :brand, :soc, :ctr, :cntry, :dept, CAST(:meta AS JSONB))"
                        ),
                        {
                            "uid": user_id,
                            "eid": ep.employee_id,
                            "brand": ep.brand,
                            "soc": ep.society,
                            "ctr": ep.center,
                            "cntry": ep.country,
                            "dept": ep.department,
                            "meta": json.dumps(ep.metadata or {}),
                        },
                    )
                    total_inserted += 1
                else:
                    total_updated += 1

    session.commit()
    _info(
        f"verification_data.{group_name}.users.ok",
        inserted=total_inserted,
        updated=total_updated,
        skipped=total_skipped,
    )
    return LoadResult(
        group=group_name,
        status="ok",
        inserted=total_inserted,
        updated=total_updated,
        skipped=total_skipped,
    )


def load_admin_users(
    session: Session,
    engine: Engine,
    fixtures: list[AdminUserFixture],
) -> LoadResult:
    """Load admin users idempotently into Postgres.

    Args:
        session:  Active SQLAlchemy sync Session.
        engine:   Engine for table-existence checks.
        fixtures: List of validated AdminUserFixture objects.

    Returns:
        LoadResult with counts and status.
    """
    _info("verification_data.admin_ai.admin_users.start", count=len(fixtures))
    if not _table_exists(engine, "users"):
        log.warning(
            "verification_data.admin_ai.deferred_until_schema_ready",
            reason="table_missing",
            table="users",
        )
        return LoadResult(group="admin_ai", status="deferred", reason="table_missing:users")

    total_inserted = total_updated = total_skipped = 0
    for fx in fixtures:
        safe_email = mask_email(str(fx.email))
        _info("verification_data.admin_ai.admin_users.upsert", email=safe_email)
        action, ins, upd, skp = _upsert_user(
            session, engine, str(fx.email), fx.full_name,
            fx.password_plain, fx.status, fx.preferred_language,
        )
        total_inserted += ins
        total_updated += upd
        total_skipped += skp

    session.commit()
    _info(
        "verification_data.admin_ai.admin_users.ok",
        inserted=total_inserted, updated=total_updated, skipped=total_skipped,
    )
    return LoadResult(
        group="admin_ai", status="ok",
        inserted=total_inserted, updated=total_updated, skipped=total_skipped,
    )


def load_rag_collections(
    session: Session,
    engine: Engine,
    fixtures: list[RagCollectionFixture],
    group_name: str = "rag_chat",
) -> LoadResult:
    """Load RAG collections idempotently into rag_collections table.

    Args:
        session:    Active SQLAlchemy sync Session.
        engine:     Engine for table-existence checks.
        fixtures:   List of RagCollectionFixture objects.
        group_name: Log label.

    Returns:
        LoadResult with counts and status.
    """
    _info(f"verification_data.{group_name}.rag_collections.start", count=len(fixtures))
    if not _table_exists(engine, "rag_collections"):
        log.warning(
            f"verification_data.{group_name}.deferred_until_schema_ready",
            reason="table_missing", table="rag_collections",
        )
        return LoadResult(group=group_name, status="deferred", reason="table_missing:rag_collections")

    total_inserted = total_updated = 0
    for fx in fixtures:
        _info(f"verification_data.{group_name}.rag_collections.upsert", name=fx.name)
        existing = session.execute(
            text("SELECT id FROM rag_collections WHERE name = :name"),
            {"name": fx.name},
        ).fetchone()
        if existing is None:
            session.execute(
                text(
                    "INSERT INTO rag_collections (name, vertical, language, enabled, metadata)"
                    " VALUES (:name, :vertical, :lang, :enabled, CAST(:meta AS JSONB))"
                ),
                {
                    "name": fx.name, "vertical": fx.vertical,
                    "lang": fx.language, "enabled": fx.enabled,
                    "meta": json.dumps(fx.metadata or {}),
                },
            )
            total_inserted += 1
        else:
            session.execute(
                text(
                    "UPDATE rag_collections SET vertical=:vertical, language=:lang,"
                    " enabled=:enabled, metadata=CAST(:meta AS JSONB) WHERE name=:name"
                ),
                {
                    "name": fx.name, "vertical": fx.vertical,
                    "lang": fx.language, "enabled": fx.enabled,
                    "meta": json.dumps(fx.metadata or {}),
                },
            )
            total_updated += 1

    session.commit()
    _info(
        f"verification_data.{group_name}.rag_collections.ok",
        inserted=total_inserted, updated=total_updated,
    )
    return LoadResult(group=group_name, status="ok", inserted=total_inserted, updated=total_updated)


def load_ai_providers(
    session: Session,
    engine: Engine,
    fixtures: list[AiProviderFixture],
) -> LoadResult:
    """Load AI providers idempotently into ai_providers table.

    Args:
        session:  Active SQLAlchemy sync Session.
        engine:   Engine for table-existence checks.
        fixtures: List of AiProviderFixture objects.

    Returns:
        LoadResult with counts and status.
    """
    _info("verification_data.admin_ai.ai_providers.start", count=len(fixtures))
    if not _table_exists(engine, "ai_providers"):
        log.warning(
            "verification_data.admin_ai.deferred_until_schema_ready",
            reason="table_missing", table="ai_providers",
        )
        return LoadResult(group="admin_ai", status="deferred", reason="table_missing:ai_providers")

    total_inserted = total_updated = 0
    for fx in fixtures:
        _info("verification_data.admin_ai.ai_providers.upsert", name=fx.name)
        existing = session.execute(
            text("SELECT id FROM ai_providers WHERE name = :name"),
            {"name": fx.name},
        ).fetchone()
        if existing is None:
            session.execute(
                text(
                    "INSERT INTO ai_providers (name, provider_type, base_url, status)"
                    " VALUES (:name, :pt, :url, :status)"
                ),
                {
                    "name": fx.name, "pt": fx.provider_type,
                    "url": fx.base_url, "status": fx.status,
                },
            )
            total_inserted += 1
        else:
            session.execute(
                text(
                    "UPDATE ai_providers SET provider_type=:pt, base_url=:url,"
                    " status=:status WHERE name=:name"
                ),
                {
                    "name": fx.name, "pt": fx.provider_type,
                    "url": fx.base_url, "status": fx.status,
                },
            )
            total_updated += 1

    session.commit()
    _info(
        "verification_data.admin_ai.ai_providers.ok",
        inserted=total_inserted, updated=total_updated,
    )
    return LoadResult(group="admin_ai", status="ok", inserted=total_inserted, updated=total_updated)


def load_mcp_servers(
    session: Session,
    engine: Engine,
    fixtures: list[McpServerFixture],
) -> LoadResult:
    """Load MCP servers idempotently into mcp_servers table.

    Args:
        session:  Active SQLAlchemy sync Session.
        engine:   Engine for table-existence checks.
        fixtures: List of McpServerFixture objects.

    Returns:
        LoadResult with counts and status.
    """
    _info("verification_data.mcp_agents.mcp_servers.start", count=len(fixtures))
    if not _table_exists(engine, "mcp_servers"):
        log.warning(
            "verification_data.mcp_agents.deferred_until_schema_ready",
            reason="table_missing", table="mcp_servers",
        )
        return LoadResult(group="mcp_agents", status="deferred", reason="table_missing:mcp_servers")

    total_inserted = total_updated = 0
    for fx in fixtures:
        _info("verification_data.mcp_agents.mcp_servers.upsert", name=fx.name)
        existing = session.execute(
            text("SELECT id FROM mcp_servers WHERE name = :name"),
            {"name": fx.name},
        ).fetchone()
        if existing is None:
            session.execute(
                text(
                    "INSERT INTO mcp_servers (name, transport_type, endpoint_url, command, status)"
                    " VALUES (:name, :tt, :url, :cmd, :status)"
                ),
                {
                    "name": fx.name, "tt": fx.transport_type,
                    "url": fx.endpoint_url, "cmd": fx.command, "status": fx.status,
                },
            )
            total_inserted += 1
        else:
            session.execute(
                text(
                    "UPDATE mcp_servers SET transport_type=:tt, endpoint_url=:url,"
                    " command=:cmd, status=:status WHERE name=:name"
                ),
                {
                    "name": fx.name, "tt": fx.transport_type,
                    "url": fx.endpoint_url, "cmd": fx.command, "status": fx.status,
                },
            )
            total_updated += 1

    session.commit()
    _info(
        "verification_data.mcp_agents.mcp_servers.ok",
        inserted=total_inserted, updated=total_updated,
    )
    return LoadResult(group="mcp_agents", status="ok", inserted=total_inserted, updated=total_updated)


def load_agents(
    session: Session,
    engine: Engine,
    fixtures: list[AgentFixture],
) -> LoadResult:
    """Load agents idempotently into agents table.

    Args:
        session:  Active SQLAlchemy sync Session.
        engine:   Engine for table-existence checks.
        fixtures: List of AgentFixture objects.

    Returns:
        LoadResult with counts and status.
    """
    _info("verification_data.mcp_agents.agents.start", count=len(fixtures))
    if not _table_exists(engine, "agents"):
        log.warning(
            "verification_data.mcp_agents.deferred_until_schema_ready",
            reason="table_missing", table="agents",
        )
        return LoadResult(group="mcp_agents", status="deferred", reason="table_missing:agents")

    total_inserted = total_updated = 0
    for fx in fixtures:
        _info("verification_data.mcp_agents.agents.upsert", name=fx.name)
        existing = session.execute(
            text("SELECT id FROM agents WHERE name = :name"),
            {"name": fx.name},
        ).fetchone()
        if existing is None:
            session.execute(
                text(
                    "INSERT INTO agents (name, description, enabled, config)"
                    " VALUES (:name, :desc, :enabled, CAST(:config AS JSONB))"
                ),
                {
                    "name": fx.name, "desc": fx.description,
                    "enabled": fx.enabled,
                    "config": json.dumps(fx.config_jsonb or {}),
                },
            )
            total_inserted += 1
        else:
            session.execute(
                text(
                    "UPDATE agents SET description=:desc, enabled=:enabled,"
                    " config=CAST(:config AS JSONB) WHERE name=:name"
                ),
                {
                    "name": fx.name, "desc": fx.description,
                    "enabled": fx.enabled,
                    "config": json.dumps(fx.config_jsonb or {}),
                },
            )
            total_updated += 1

    session.commit()
    _info(
        "verification_data.mcp_agents.agents.ok",
        inserted=total_inserted, updated=total_updated,
    )
    return LoadResult(group="mcp_agents", status="ok", inserted=total_inserted, updated=total_updated)
