"""
Hilo People — Mail module facade.

Slice:  P01-S02-T005 — forgot + reset password email dispatch.
        Debugger cycle 1 — split sender.py into mailer_base + 3 concrete
                            files (validator F2; "1 component per file").
Phase:  P01 Auth + Data Foundation
Purpose: Public API for the mail subsystem. Callers import the Mailer ABC
         and the get_mailer() factory from here; the concrete Mailer
         implementation is selected via the MAIL_MODE env var.

Modes:
  - MAIL_MODE=outbox  (default dev/CI): OutboxMailer writes JSONL.
  - MAIL_MODE=resend:                   ResendMailer (SDK lazy-imported).
  - MAIL_MODE=smtp:                     SmtpMailer with STARTTLS port 587.

Submodules:
  - mailer_base.py   — Mailer ABC + shared helpers + SUBJECT_MAP constant.
  - outbox_mailer.py — OutboxMailer (dev/CI JSONL).
  - resend_mailer.py — ResendMailer (production transactional API).
  - smtp_mailer.py   — SmtpMailer (SMTP fallback).

Source refs:
  - task pack §I-7 (mail module structure), §M.3 (mode selection).
  - TECHNICAL_GUIDE §10.1 fila 52 (resend + SMTP fallback).
"""

from __future__ import annotations

import os

from app.mail.mailer_base import Mailer
from app.mail.outbox_mailer import OutboxMailer
from app.mail.smtp_mailer import SmtpMailer

__all__ = ["Mailer", "OutboxMailer", "SmtpMailer", "get_mailer", "reset_mailer"]

_mailer_instance: Mailer | None = None


def get_mailer() -> Mailer:
    """Return the configured Mailer instance (module-level singleton).

    Selected via MAIL_MODE env var:
      - 'outbox' (default): append-only JSONL in orchestrator-state/dev-logs/.
      - 'resend': ResendMailer using RESEND_API_KEY (lazy import).
      - 'smtp': SmtpMailer using MAIL_SMTP_* env vars.

    Returns:
        Mailer: Concrete mailer implementation.
    """
    global _mailer_instance
    if _mailer_instance is not None:
        return _mailer_instance

    mode = os.getenv("MAIL_MODE", "outbox").lower()

    if mode == "resend":
        # Lazy import — only load the resend SDK when configured.
        from app.mail.resend_mailer import ResendMailer  # noqa: PLC0415

        _mailer_instance = ResendMailer()
    elif mode == "smtp":
        _mailer_instance = SmtpMailer()
    else:
        _mailer_instance = OutboxMailer()

    return _mailer_instance


def reset_mailer() -> None:
    """Reset the singleton (for testing — allows different MAIL_MODE per test)."""
    global _mailer_instance
    _mailer_instance = None
