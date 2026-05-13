"""
Hilo People — Admin AI providers service (orchestration layer).

Slice:  P02-S05-T001 — Admin AI providers and models endpoints (debugger cycle 1, §D-AASPLIT)
Phase:  P02 Core Features
Purpose: Orchestrates the provider-creation use case: invokes the repository,
         commits/rolls back the main transaction, and triggers the audit
         writer with the right outcome. Also hosts the singleton RateLimiter
         used by POST /providers so the router stays handler-only.

Key deps:
  - app.admin.providers.repository.create_provider
  - app.admin.providers.audit.write_provider_audit
  - app.security.rate_limit.RateLimiter
  - app.security.encryption.EncryptionError

Source refs:
  - task pack P02-S05-T001 §D-RL1 (rate limit only on POST /providers)
  - task pack P02-S05-T001 §D-S2 (audit independent session)

Decisions:
  - D-RL1: ADMIN_AI prefix, 20/min/IP, burst=20, window=60s. Production-only
    config — test fixtures clear the bucket; tests do not rebuild this
    limiter so its identity in the dependency graph stays stable.
  - Service raises EncryptionError up to the router so the router can decide
    response shape (5xx envelope) without coupling repository → HTTP.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.admin.providers.audit import write_provider_audit
from app.admin.providers.repository import create_provider as _repo_create
from app.db.models.admin_ai import AiProvider
from app.security.encryption import EncryptionError
from app.security.rate_limit import RateLimiter

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Singleton rate limiter for POST /providers (D-RL1)
# ---------------------------------------------------------------------------
create_provider_limiter = RateLimiter(
    prefix="ADMIN_AI",
    per_minute=20,
    burst=20,
    window_seconds=60,
)


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
    request_id: str,
    ip: str,
    user_agent: str,
) -> AiProvider:
    """Orchestrate the create-provider use case (encrypt, persist, audit).

    On success: commits the main tx and writes a `success` audit row.
    On EncryptionError: rolls back and writes a `failure` audit row, then
    re-raises so the router emits a 500 envelope.
    On any other exception: rolls back and writes a `failure` audit row, then
    re-raises.

    Args:
        session:             Active SQLAlchemy Session (will be committed).
        provider_type:       Provider type key.
        name:                Human-readable name.
        base_url:            Optional base URL.
        auth_type:           Credential kind.
        secret_plain:        Raw API secret (NEVER logged).
        refresh_token_plain: Optional refresh token (NEVER logged).
        expires_at:          Optional token expiry.
        created_by:          Admin user UUID.
        request_id:          X-Request-ID for audit metadata.
        ip:                  Client IP for audit metadata.
        user_agent:          User-Agent header for audit metadata.

    Returns:
        Persisted AiProvider ORM instance.

    Raises:
        EncryptionError: When Fernet encryption fails.
        Exception:       On any other persistence failure.
    """
    if _VERBOSE:
        logger.debug(
            "admin.providers.service.create.start provider_type=%s "
            "name_len=%d request_id=%s",
            provider_type,
            len(name),
            request_id,
        )  # BEFORE — credentials intentionally omitted

    try:
        provider = _repo_create(
            session,
            provider_type=provider_type,
            name=name,
            base_url=base_url,
            auth_type=auth_type,
            secret_plain=secret_plain,
            refresh_token_plain=refresh_token_plain,
            expires_at=expires_at,
            created_by=created_by,
        )
        session.commit()
    except EncryptionError as exc:
        logger.error(
            "admin.providers.service.create.encryption_error request_id=%s error=%s",
            request_id,
            type(exc).__name__,
        )
        session.rollback()
        # D-S2: write audit with outcome=failure even though main tx rolled back.
        write_provider_audit(
            actor_user_id=created_by,
            provider_id=uuid.UUID(int=0),  # placeholder — no entity was created
            name=name,
            provider_type=provider_type,
            request_id=request_id,
            ip=ip,
            user_agent=user_agent,
            outcome="failure",
        )
        raise
    except Exception as exc:
        logger.error(
            "admin.providers.service.create.error request_id=%s error=%s",
            request_id,
            type(exc).__name__,
            exc_info=True,
        )
        session.rollback()
        write_provider_audit(
            actor_user_id=created_by,
            provider_id=uuid.UUID(int=0),
            name=name,
            provider_type=provider_type,
            request_id=request_id,
            ip=ip,
            user_agent=user_agent,
            outcome="failure",
        )
        raise

    # Audit after successful commit (D-S2 — independent session).
    write_provider_audit(
        actor_user_id=created_by,
        provider_id=provider.id,
        name=provider.name,
        provider_type=provider.provider_type,
        request_id=request_id,
        ip=ip,
        user_agent=user_agent,
        outcome="success",
    )

    if _VERBOSE:
        logger.debug(
            "admin.providers.service.create.ok provider_id=%s request_id=%s",
            str(provider.id),
            request_id,
        )  # AFTER
    return provider
