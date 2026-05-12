"""
Hilo People — OutboxMailer: dev/CI append-only JSONL outbox.

Slice:  P01-S02-T005 — debugger cycle 1 (extracted from mail/sender.py per
                       validator F2 — 1 component per file).
Phase:  P01 Auth + Data Foundation
Purpose: Default dev/CI mailer. Writes outgoing email metadata (and the
         raw token, for integration tests) to a JSONL outbox file. Sends
         NOTHING over the network. Tests inspect the JSONL to drive the
         reset flow without a real provider.

Configured via:
  MAIL_OUTBOX_PATH — optional path override; defaults to canonical
                     orchestrator-state/dev-logs/mail-outbox.jsonl.

Source refs:
  - task pack §M.3 (mode selection), §H-forgot-10 (dev mode contract).
  - 01-non-negotiables.md §Security (no PII/tokens in logs).
"""

from __future__ import annotations

import logging

from app.mail.mailer_base import Mailer, render_reset_email
from app.mail.outbox import append_to_outbox

logger = logging.getLogger(__name__)


class OutboxMailer(Mailer):
    """Dev-mode mailer: writes email metadata to a JSONL outbox file.

    Does NOT send any email over the network. The raw_token is stored in
    the outbox entry so integration tests can extract it and drive the
    reset flow without a real mail provider.
    """

    def send_reset_email(
        self,
        *,
        to: str,
        user_email: str,
        raw_token: str,
        locale: str,
        request_id: str,
    ) -> None:
        """Write outgoing reset email to the dev JSONL outbox."""
        to_domain = to.split("@")[-1] if "@" in to else "unknown"
        logger.debug(
            "mail.outbox.send_reset_email.start to_domain=%s locale=%s",
            to_domain,
            locale,
        )  # BEFORE — domain only, no full email

        subject, html, text, sl = render_reset_email(
            user_email=user_email,
            raw_token=raw_token,
            locale=locale,
        )

        append_to_outbox(
            to=to,
            subject=subject,
            locale=sl,
            template="reset_password",
            html_len=len(html),
            text_len=len(text),
            request_id=request_id,
            token=raw_token,  # stored for test extraction (dev only)
        )

        logger.debug(
            "mail.outbox.send_reset_email.done to_domain=%s locale=%s html_len=%d",
            to_domain,
            sl,
            len(html),
        )  # AFTER
