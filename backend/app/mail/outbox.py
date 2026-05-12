"""
Hilo People — Dev-mode mail outbox: append-only JSONL writer.

Slice:  P01-S02-T005 — forgot + reset password email dispatch
Phase:  P01 Auth + Data Foundation
Purpose: In dev/CI mode (MAIL_MODE=outbox), appends each outgoing email as
         a JSON line to orchestrator-state/dev-logs/mail-outbox.jsonl instead
         of calling any real mail provider. Tests read this file to verify
         mail dispatch without network I/O.

Key deps:
  - pathlib, json, datetime (stdlib only — no third-party deps in dev mode)

Security:
  - Logs html_len / text_len, NOT the HTML body (token would be embedded).
  - The raw reset token is stored in the 'token' key ONLY for test readability
    (outbox is a dev-only ledger, never deployed to production).

Source refs:
  - task pack §I-7, §M.3, §H-forgot-10 (dev mode outbox)
  - task pack §J tests T01/T21 (tests read outbox JSONL)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default outbox path — can be overridden via MAIL_OUTBOX_PATH env var for testing
_DEFAULT_OUTBOX = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "orchestrator-state"
    / "dev-logs"
    / "mail-outbox.jsonl"
)


def _outbox_path() -> Path:
    """Return the configured outbox file path."""
    env_path = os.getenv("MAIL_OUTBOX_PATH")
    if env_path:
        return Path(env_path)
    return _DEFAULT_OUTBOX


def append_to_outbox(
    *,
    to: str,
    subject: str,
    locale: str,
    template: str,
    html_len: int,
    text_len: int,
    request_id: str,
    token: Optional[str] = None,
) -> None:
    """Append one outgoing email to the dev outbox JSONL file.

    The raw reset token is included for test readability (tests extract it
    to drive the reset flow). The HTML body is NOT stored (contains the token
    in a link — storing the full body would be redundant and verbose).

    Args:
        to: Recipient email address.
        subject: Localised email subject line.
        locale: Template locale used (es/en/fr).
        template: Template name (e.g. 'reset_password').
        html_len: Length in chars of rendered HTML (for size verification).
        text_len: Length in chars of rendered plain text.
        request_id: X-Request-ID for correlation.
        token: Optional raw reset token (stored for test extraction).
    """
    outbox = _outbox_path()
    outbox.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "ts": datetime.now(tz=timezone.utc).isoformat(),
        "to": to,
        "subject": subject,
        "locale": locale,
        "template": template,
        "html_len": html_len,
        "text_len": text_len,
        "request_id": request_id,
    }
    if token is not None:
        entry["token"] = token

    logger.debug(
        "mail.outbox.append.start to_domain=%s locale=%s template=%s",
        to.split("@")[-1] if "@" in to else "unknown",
        locale,
        template,
    )  # BEFORE — domain only, never full email

    with open(outbox, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    logger.debug(
        "mail.outbox.append.done template=%s locale=%s",
        template,
        locale,
    )  # AFTER
