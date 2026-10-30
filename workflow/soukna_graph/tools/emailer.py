# =====================================================================
# Canal email — SMTP (starttls sur 587, SSL implicite sur 465).
# Beaucoup d'hébergeurs cloud bloquent le SMTP sortant : le détail
# d'erreur inclut le message OS exact (refusé / timeout / unreachable).
# =====================================================================
from __future__ import annotations

import smtplib
from email.mime.text import MIMEText

from .. import config


def _smtp_send(to: str, msg: MIMEText) -> tuple[bool, str]:
    try:
        if config.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(config.SMTP_HOST, 465, timeout=30) as server:
                if config.SMTP_USER:
                    server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.sendmail(config.SMTP_FROM, [to], msg.as_string())
        else:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as server:
                server.starttls()
                if config.SMTP_USER:
                    server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.sendmail(config.SMTP_FROM, [to], msg.as_string())
        return True, "sent"
    except (smtplib.SMTPException, OSError) as exc:
        return False, f"smtp:{type(exc).__name__}:{exc}"[:200]


def send_email(to: str, subject: str, body: str) -> tuple[bool, str]:
    """Envoie un email texte. Retourne (envoyé, détail)."""
    if not config.email_ready():
        return False, "email_not_configured"
    if not to:
        return False, "recipient_missing"
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = config.SMTP_FROM
    msg["To"] = to
    return _smtp_send(to, msg)


def send_email_html(to: str, subject: str, html: str) -> tuple[bool, str]:
    """Envoie un email HTML (invitation client). Retourne (envoyé, détail)."""
    if not config.email_ready():
        return False, "email_not_configured"
    if not to:
        return False, "recipient_missing"
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = config.SMTP_FROM
    msg["To"] = to
    return _smtp_send(to, msg)
