"""
Hilo People — Audit writer for users.language.update events (D-S2 pattern).

Slice:  P01-S02-T007 — PATCH /api/v1/users/me/language
Phase:  P01 Auth + Data Foundation
Purpose: Encapsulates writing an audit_logs row for the language update event.
         Uses an independent DB session (audit_session_scope) so the audit row
         persists even if the caller's main transaction rolls back (D-S2 pattern,
         same as LogoutAuditWriter in P01-S02-T004).

Dependencies:
  - app.db.session.audit_session_scope — independent audit session (D-S2)
  - app.db.models.auth.AuditLog — ORM model for audit_logs table
  - uuid — standard library

Source refs:
  - task pack §F.2 (audit log contract: action, actor_user_id, metadata)
  - task pack §G.15 (D-S2 failure audit for PATCH)
  - task pack §G.6 (idempotent PATCH still writes audit row)
  - task pack §T13 / §T23 (test requirements: no PII in metadata)
  - 01-non-negotiables.md §Security/Audit log (GDPR Art. 30)

Decisions:
  - AuditLog has no outcome/ip_address/user_agent columns — all contextual data
    goes into extra_metadata (JSONB). This matches the T003/T004 pattern.
  - metadata carries {request_id, ip, user_agent, from, to, outcome} — no email/name/token.
  - 'from' and 'to' are language codes (es/en/fr) — not considered PII.
  - 'outcome' distinguishes success from failure paths.
  - entity_id is the user UUID (UUID type required by ORM).
  - G.15: For the 401 path BEFORE token decode, no audit row is possible (no actor).
"""

from __future__ import annotations

import logging
import uuid

from app.db.models.auth import AuditLog
from app.db.session import audit_session_scope

logger = logging.getLogger(__name__)


class LanguageUpdateAuditWriter:
    """Write a users.language.update audit row using an independent DB session.

    Follows the D-S2 pattern from P01-S02-T003/T004: the audit write uses a
    session separate from the caller's main transaction so the row persists
    even on rollback.

    Usage:
        writer = LanguageUpdateAuditWriter(
            actor_user_id=user.id,
            from_language="es",
            to_language="en",
            request_id="uuid-here",
            ip="1.2.3.4",
        )
        writer.write(outcome="success")
    """

    def __init__(
        self,
        actor_user_id: uuid.UUID,
        from_language: str,
        to_language: str,
        request_id: str,
        ip: str,
        user_agent: str = "",
    ) -> None:
        """Initialise audit writer with event context.

        Args:
            actor_user_id: UUID of the user performing the language update.
            from_language: Previous language code (e.g. 'es').
            to_language: New language code (e.g. 'en').
            request_id: X-Request-ID correlation header value.
            ip: Client IP address (from X-Forwarded-For or request.client.host).
            user_agent: User-Agent header value (optional).
        """
        self._actor_user_id = actor_user_id
        self._from_language = from_language
        self._to_language = to_language
        self._request_id = request_id
        self._ip = ip
        self._user_agent = user_agent

    def write(self, outcome: str = "success") -> None:
        """Write the audit_logs row using an independent session (D-S2).

        All contextual data (ip, user_agent, from, to, outcome) goes into
        extra_metadata (JSONB) — the AuditLog table has no dedicated columns
        for those fields (matches T003/T004 audit pattern).

        Args:
            outcome: Audit outcome string. 'success' for happy path.
                     'unauthorized' for inactive user path (G.15).

        Raises:
            Exception: On DB failure — logged as ERROR, not re-raised (audit
                       write failure must not surface to the client as a 500).
        """
        logger.debug(
            "users.audit.language_update.start actor_user_id=%s from=%s to=%s outcome=%s",
            str(self._actor_user_id),
            self._from_language,
            self._to_language,
            outcome,
        )  # BEFORE
        try:
            with audit_session_scope() as audit_session:
                row = AuditLog(
                    actor_user_id=self._actor_user_id,
                    action="users.language.update",
                    entity_type="user",
                    entity_id=self._actor_user_id,
                    extra_metadata={
                        "request_id": self._request_id,
                        "ip": self._ip,
                        "user_agent": self._user_agent,
                        "from": self._from_language,
                        "to": self._to_language,
                        "outcome": outcome,
                    },
                )
                audit_session.add(row)
                audit_session.commit()
            logger.debug(
                "users.audit.language_update.done actor_user_id=%s outcome=%s",
                str(self._actor_user_id),
                outcome,
            )  # AFTER
        except Exception as exc:
            logger.error(
                "users.audit.language_update.error actor_user_id=%s outcome=%s error=%s",
                str(self._actor_user_id),
                outcome,
                str(exc),
                exc_info=True,
            )
