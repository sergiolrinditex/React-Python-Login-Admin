"""
Hilo People — ResendMailer: Resend transactional API mailer.

Slice:  P01-S02-T005 — debugger cycle 1 (extracted from mail/sender.py per
                       validator F2 — 1 component per file).
Phase:  P01 Auth + Data Foundation
Purpose: Production mailer that uses the Resend SDK (resend==2.30.0).
         Resend is imported lazily inside __init__ so dev/CI environments
         without RESEND_API_KEY never pay the import cost or risk an
         import-time SDK failure.

API pattern (resend 2.30.0):
    import resend
    resend.api_key = RESEND_API_KEY
    resend.Emails.send({from, to, subject, html, text, headers})

Source refs:
  - task pack §M.3 (mode selection), §I-7 (mail module).
  - TECHNICAL_GUIDE §10.1 fila 52 (resend + SMTP fallback).
  - official-doc-notes/P01-S02-T005-resend-mail-2026-05-12.md (RESOLVED).
"""

from __future__ import annotations

import logging
import os

from app.mail.mailer_base import DEFAULT_FROM, Mailer, render_reset_email

logger = logging.getLogger(__name__)


class ResendMailer(Mailer):
    """Production mailer: sends via the Resend SDK.

    Raises propagate on Resend 4xx/5xx so callers can decide whether to
    swallow (anti-enum forgot-password is best-effort) or surface them.
    """

    def __init__(self) -> None:
        """Initialise the Resend SDK with the API key from env."""
        import resend as _resend  # noqa: PLC0415 — lazy import

        api_key = os.getenv("RESEND_API_KEY", "")
        if not api_key:
            logger.warning("mail.resend.init.no_api_key RESEND_API_KEY not set")
        _resend.api_key = api_key
        self._resend = _resend

    def send_reset_email(
        self,
        *,
        to: str,
        user_email: str,
        raw_token: str,
        locale: str,
        request_id: str,
    ) -> None:
        """Send a reset email via the Resend transactional API."""
        to_domain = to.split("@")[-1] if "@" in to else "unknown"
        logger.debug(
            "mail.resend.send_reset_email.start to_domain=%s locale=%s",
            to_domain,
            locale,
        )  # BEFORE

        subject, html, text, sl = render_reset_email(
            user_email=user_email,
            raw_token=raw_token,
            locale=locale,
        )

        mail_from = os.getenv("MAIL_FROM", DEFAULT_FROM)
        params = {
            "from": mail_from,
            "to": [to],
            "subject": subject,
            "html": html,
            "text": text,
            "headers": {"X-Request-ID": request_id},
        }

        try:
            self._resend.Emails.send(params)
            logger.debug(
                "mail.resend.send_reset_email.done to_domain=%s locale=%s",
                to_domain,
                sl,
            )  # AFTER
        except Exception:
            logger.error(
                "mail.resend.send_reset_email.error to_domain=%s",
                to_domain,
                exc_info=True,
            )  # ERROR
            raise
