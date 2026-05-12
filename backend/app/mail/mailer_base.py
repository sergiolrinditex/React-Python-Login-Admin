"""
Hilo People — Mailer abstract base + shared helpers + SUBJECT_MAP constant.

Slice:  P01-S02-T005 — debugger cycle 1 (split per validator F2: extract
                       the ABC + shared helpers into one module so each
                       concrete Mailer lives in its own file, "1 component
                       per file" rule from 01-non-negotiables.md).
Phase:  P01 Auth + Data Foundation
Purpose: Define the Mailer ABC and provide the helpers and constants
         shared by every concrete implementation (OutboxMailer / ResendMailer
         / SmtpMailer). The DRY violation flagged by the validator
         (subject_map duplicated three times) is fixed by promoting
         SUBJECT_MAP to a single module-level constant here.

Key deps:
  - Stdlib only (Path, logging, abc).

Source refs:
  - task pack §I-7 (mail module), §M.3 (mode selection), §H-forgot-10 (dev).
  - TECHNICAL_GUIDE §10.1 fila 52 (resend + SMTP fallback).
  - 01-non-negotiables.md §Security (no PII/tokens in logs), §File size.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
SUPPORTED_LOCALES = ("es", "en", "fr")
DEFAULT_LOCALE = "es"
DEFAULT_FROM = "noreply@inditex-sandbox.com"

# Single source for the localised subject lines. Previously this dict was
# duplicated in OutboxMailer + ResendMailer + SmtpMailer (DRY violation
# flagged by validator). Concrete mailers now call resolve_subject(locale).
SUBJECT_MAP: dict[str, str] = {
    "es": "Restablece tu contraseña — Hilo People",
    "en": "Reset your password — Hilo People",
    "fr": "Réinitialisez votre mot de passe — Hilo People",
}


def safe_locale(locale: str) -> str:
    """Return a supported locale, falling back to DEFAULT_LOCALE."""
    return locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE


def resolve_subject(locale: str) -> str:
    """Return the localised reset-email subject line."""
    return SUBJECT_MAP.get(safe_locale(locale), SUBJECT_MAP[DEFAULT_LOCALE])


def load_template(template: str, locale: str, fmt: str) -> str:
    """Load a localised email template from the templates directory.

    Args:
        template: Template base name (e.g. 'reset_password').
        locale: Locale code ('es', 'en', 'fr'). Falls back to DEFAULT_LOCALE.
        fmt: Format ('html' or 'txt').

    Returns:
        Template file contents as a string.
    """
    sl = safe_locale(locale)
    filename = f"{template}_{sl}.{fmt}"
    path = _TEMPLATES_DIR / filename
    if not path.exists():
        # Fallback to default locale if the requested locale file is missing.
        filename = f"{template}_{DEFAULT_LOCALE}.{fmt}"
        path = _TEMPLATES_DIR / filename
    return path.read_text(encoding="utf-8")


def render(template_str: str, context: dict) -> str:
    """Substitute {{key}} placeholders in a template string.

    Args:
        template_str: Template content with {{key}} markers.
        context: Dict of substitution values.

    Returns:
        Rendered string.
    """
    result = template_str
    for key, value in context.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result


def build_reset_url(raw_token: str) -> str:
    """Build the frontend reset URL with the raw token in the query string.

    Args:
        raw_token: URL-safe raw reset token (emailed to user). NEVER log.

    Returns:
        Full URL the user clicks to reset their password.
    """
    base = os.getenv("APP_BASE_URL", "http://localhost:5173").rstrip("/")
    return f"{base}/auth/reset?token={raw_token}"


def render_reset_email(
    *,
    user_email: str,
    raw_token: str,
    locale: str,
) -> tuple[str, str, str, str]:
    """Render the reset email artefacts shared by every concrete mailer.

    Returns:
        Tuple (subject, html, text, safe_locale_used).
    """
    sl = safe_locale(locale)
    subject = resolve_subject(sl)
    reset_url = build_reset_url(raw_token)
    context = {"user_email": user_email, "reset_url": reset_url}
    html = render(load_template("reset_password", sl, "html"), context)
    text = render(load_template("reset_password", sl, "txt"), context)
    return subject, html, text, sl


class Mailer(ABC):
    """Abstract mailer interface.

    All concrete mailers must implement send_reset_email.
    """

    @abstractmethod
    def send_reset_email(
        self,
        *,
        to: str,
        user_email: str,
        raw_token: str,
        locale: str,
        request_id: str,
    ) -> None:
        """Send a password reset email.

        Args:
            to: Recipient address (same as user_email in most cases).
            user_email: Display email shown in the template body.
            raw_token: URL-safe reset token (embedded in link URL). NEVER log.
            locale: Preferred locale (es/en/fr).
            request_id: X-Request-ID for correlation in outbox/logs.
        """
