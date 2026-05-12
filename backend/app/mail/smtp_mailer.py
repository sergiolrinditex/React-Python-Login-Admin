"""
Hilo People — SmtpMailer: stdlib smtplib STARTTLS fallback.

Slice:  P01-S02-T005 — debugger cycle 1 (extracted from mail/sender.py per
                       validator F2 — 1 component per file).
Phase:  P01 Auth + Data Foundation
Purpose: SMTP fallback for environments without Resend. Uses sync
         smtplib + STARTTLS on port 587 — acceptable for P01 (router
         handlers are def, FastAPI runs them via threadpool, no event
         loop blocking).

Configured via:
  MAIL_SMTP_HOST, MAIL_SMTP_PORT (default 587),
  MAIL_SMTP_USER, MAIL_SMTP_PASS, MAIL_FROM.

Source refs:
  - task pack §M.3 (mode selection), §I-7 (mail module).
  - TECHNICAL_GUIDE §10.1 fila 52 (SMTP fallback).
  - official-doc-notes/P01-S02-T005-resend-mail-2026-05-12.md (RESOLVED:
    sync smtplib is fine in a sync FastAPI handler).
"""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.mail.mailer_base import DEFAULT_FROM, Mailer, render_reset_email

logger = logging.getLogger(__name__)


class SmtpMailer(Mailer):
    """SMTP fallback mailer using stdlib smtplib with STARTTLS (port 587)."""

    def send_reset_email(
        self,
        *,
        to: str,
        user_email: str,
        raw_token: str,
        locale: str,
        request_id: str,
    ) -> None:
        """Send a reset email via SMTP with STARTTLS.

        Raises:
            smtplib.SMTPException: On SMTP delivery failure.
        """
        to_domain = to.split("@")[-1] if "@" in to else "unknown"
        logger.debug(
            "mail.smtp.send_reset_email.start to_domain=%s locale=%s",
            to_domain,
            locale,
        )  # BEFORE

        subject, html, text, _sl = render_reset_email(
            user_email=user_email,
            raw_token=raw_token,
            locale=locale,
        )

        mail_from = os.getenv("MAIL_FROM", DEFAULT_FROM)
        smtp_host = os.getenv("MAIL_SMTP_HOST", "localhost")
        smtp_port = int(os.getenv("MAIL_SMTP_PORT", "587"))
        smtp_user = os.getenv("MAIL_SMTP_USER", "")
        smtp_pass = os.getenv("MAIL_SMTP_PASS", "")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = mail_from
        msg["To"] = to
        msg["X-Request-ID"] = request_id
        msg.attach(MIMEText(text, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        try:
            context_ssl = ssl.create_default_context()
            with smtplib.SMTP(smtp_host, smtp_port) as smtp:
                smtp.ehlo()
                smtp.starttls(context=context_ssl)
                smtp.ehlo()
                if smtp_user:
                    smtp.login(smtp_user, smtp_pass)
                smtp.sendmail(mail_from, [to], msg.as_string())
            logger.debug(
                "mail.smtp.send_reset_email.done to_domain=%s",
                to_domain,
            )  # AFTER
        except smtplib.SMTPException:
            logger.error(
                "mail.smtp.send_reset_email.error to_domain=%s",
                to_domain,
                exc_info=True,
            )  # ERROR
            raise
