"""
Hilo People — Admin AI providers repository (DB queries only).

Slice:  P02-S05-T001 — Admin AI providers and models endpoints (debugger cycle 1, §D-AASPLIT)
Phase:  P02 Core Features
Purpose: SQLAlchemy queries against ai_providers / ai_provider_credentials.
         No business policy here — the service layer orchestrates encryption,
         transaction boundaries and audit; this module only persists.

Key deps:
  - sqlalchemy.orm.Session — sync session
  - app.db.models.admin_ai (AiProvider, AiProviderCredential)

Source refs:
  - task pack P02-S05-T001 §Front→Back→DB contract (GET /providers + POST)
  - 01-non-negotiables.md §Database (parametrized queries, indexes)

Decisions:
  - _list_providers uses LEFT JOIN LATERAL to pick the first credential row per
    provider; V1 stores at most one per provider so this is deterministic.
  - _create_provider expects the caller to commit. Encryption raising
    EncryptionError propagates up unchanged; the caller handles rollback +
    audit_outcome=failure (D-S2 pattern).
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.models.admin_ai import AiProvider, AiProviderCredential
from app.security.encryption import encrypt_secret

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def list_providers(session: Session) -> list[dict[str, Any]]:
    """Query ai_providers with credential metadata (no encrypted values).

    Performs a LEFT JOIN to ai_provider_credentials. If multiple credential
    rows exist (not expected in V1 — one per provider), the first is used.

    Args:
        session: Active SQLAlchemy sync Session.

    Returns:
        List of provider dicts (merged from ai_providers + ai_provider_credentials).
    """
    if _VERBOSE:
        logger.debug("admin.providers.repository.list.start")  # BEFORE

    rows = session.execute(
        sa.text(
            """
            SELECT
                p.id,
                p.name,
                p.provider_type,
                p.base_url,
                p.status,
                p.created_by,
                c.auth_type AS credential_auth_type,
                c.expires_at,
                (c.id IS NOT NULL) AS has_credentials
            FROM ai_providers p
            LEFT JOIN LATERAL (
                SELECT id, auth_type, expires_at
                FROM ai_provider_credentials
                WHERE provider_id = p.id
                ORDER BY id
                LIMIT 1
            ) c ON true
            ORDER BY p.name
            """
        )
    ).fetchall()

    results = [
        {
            "id": row[0],
            "name": row[1],
            "provider_type": row[2],
            "base_url": row[3],
            "status": row[4],
            "created_by": row[5],
            "credential_auth_type": row[6],
            "expires_at": row[7],
            "has_credentials": bool(row[8]),
        }
        for row in rows
    ]

    if _VERBOSE:
        logger.debug(
            "admin.providers.repository.list.ok count=%d", len(results)
        )  # AFTER
    return results


def create_provider(
    session: Session,
    *,
    provider_type: str,
    name: str,
    base_url: str | None,
    auth_type: str,
    secret_plain: str,
    refresh_token_plain: str | None,
    expires_at: datetime | None,
    created_by: uuid.UUID,
) -> AiProvider:
    """Insert ai_providers + ai_provider_credentials in a single transaction.

    Encrypts secret_plain (and optional refresh_token_plain) with Fernet
    before persistence. NEVER logs the plaintext or ciphertext values.

    Args:
        session:             Active SQLAlchemy Session (caller commits).
        provider_type:       Provider type key.
        name:                Human-readable name.
        base_url:            Optional base URL.
        auth_type:           Credential kind.
        secret_plain:        Raw API secret — encrypted here.
        refresh_token_plain: Optional raw OAuth2 refresh token.
        expires_at:          Optional token expiry.
        created_by:          Admin user UUID.

    Returns:
        Newly created AiProvider ORM instance (post-flush, id assigned by DB).

    Raises:
        EncryptionError: If Fernet encryption fails (caller handles rollback).
    """
    if _VERBOSE:
        logger.debug(
            "admin.providers.repository.create.start provider_type=%s name_len=%d",
            provider_type,
            len(name),
        )  # BEFORE

    # Encrypt credentials before any DB write so an EncryptionError aborts the
    # whole operation (no partial provider row left behind).
    encrypted_secret = encrypt_secret(secret_plain)
    encrypted_refresh: str | None = None
    if refresh_token_plain:
        encrypted_refresh = encrypt_secret(refresh_token_plain)

    provider = AiProvider(
        name=name,
        provider_type=provider_type,
        base_url=base_url,
        status="draft",
        created_by=created_by,
    )
    session.add(provider)
    session.flush()  # materialise provider.id before inserting credential

    credential = AiProviderCredential(
        provider_id=provider.id,
        auth_type=auth_type,
        encrypted_secret=encrypted_secret,
        encrypted_refresh_token=encrypted_refresh,
        expires_at=expires_at,
    )
    session.add(credential)
    session.flush()

    if _VERBOSE:
        logger.debug(
            "admin.providers.repository.create.ok provider_id=%s",
            str(provider.id),
        )  # AFTER — no credential values logged
    return provider
