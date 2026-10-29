# =====================================================================
# Canal email (digest quotidien) — SMTP starttls, désactivé silencieusement
# si SMTP_HOST est vide (carte digest : « canal simplement ignoré »).
# =====================================================================
from __future__ import annotations

import smtplib
from email.mime.text import MIMEText

from .. import config


def send_email(to: str, subject: str, body: str) -> tuple[bool, str]:
    """Envoie un email texte. Retourne (envoyé, détail)."""
    if not config.email_ready() or not to:
        return False, "email_not_configured"
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = config.SMTP_FROM
        msg["To"] = to
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as server:
            server.starttls()
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.sendmail(config.SMTP_FROM, [to], msg.as_string())
        return True, "sent"
    except (smtplib.SMTPException, OSError) as exc:
        return False, f"smtp:{type(exc).__name__}"


def send_email_html(to: str, subject: str, html: str) -> tuple[bool, str]:
    """Envoie un email HTML (invitation client). Retourne (envoyé, détail)."""
    if not config.email_ready() or not to:
        return False, "email_not_configured"
    try:
        msg = MIMEText(html, "html", "utf-8")
        msg["Subject"] = subject
        msg["From"] = config.SMTP_FROM
        msg["To"] = to
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as server:
            server.starttls()
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.sendmail(config.SMTP_FROM, [to], msg.as_string())
        return True, "sent"
    except (smtplib.SMTPException, OSError) as exc:
        return False, f"smtp:{type(exc).__name__}"
