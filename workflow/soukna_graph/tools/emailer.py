# =====================================================================
# Canal email — deux voies, même contrat (envoyé, détail) :
#   1. Brevo API HTTPS (production) : les hébergeurs cloud bloquent le
#      SMTP sortant (Errno 101 sur 587/465), jamais HTTPS. Prioritaire
#      si BREVO_API_KEY est défini.
#   2. SMTP classique (local / docker compose) : starttls 587 ou SSL 465.
# =====================================================================
from __future__ import annotations

import smtplib
from email.mime.text import MIMEText

import requests

from .. import config

_BREVO_URL = "https://api.brevo.com/v3/smtp/email"
_RESEND_URL = "https://api.resend.com/emails"


def _sender_email() -> str:
    return config.SMTP_FROM if "@" in config.SMTP_FROM else config.SMTP_USER


def _send_via_resend(to: str, subject: str, html: str, text: str) -> tuple[bool, str] | None:
    """Envoie via l'API Resend. None si la clé n'est pas configurée.
    Sans domaine vérifié chez Resend, seuls les envois vers l'email du
    compte Resend sont acceptés (le 403 du API le rappelle)."""
    if not config.RESEND_API_KEY:
        return None
    try:
        r = requests.post(
            _RESEND_URL,
            headers={
                "Authorization": f"Bearer {config.RESEND_API_KEY}",
                "content-type": "application/json",
            },
            json={
                "from": _sender_email(),
                "to": [to],
                "subject": subject,
                **({"html": html} if html else {"text": text}),
            },
            timeout=30,
        )
        if r.status_code == 200:
            return True, "sent(resend)"
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        return False, f"resend_{r.status_code}:{str(body.get('message', ''))[:120]}"
    except requests.RequestException as exc:
        return False, f"resend_network:{type(exc).__name__}"


def _send_via_brevo(to: str, subject: str, html: str, text: str) -> tuple[bool, str] | None:
    """Envoie via l'API Brevo. None si la clé n'est pas configurée
    (on bascule alors sur SMTP)."""
    if not config.BREVO_API_KEY:
        return None
    sender_email = _sender_email()
    payload: dict = {
        "sender": {"name": "Soukna", "email": sender_email},
        "to": [{"email": to}],
        "subject": subject,
    }
    if html:
        payload["htmlContent"] = html
    if text:
        payload["textContent"] = text
    try:
        r = requests.post(
            _BREVO_URL,
            headers={
                "api-key": config.BREVO_API_KEY,
                "content-type": "application/json",
                "accept": "application/json",
            },
            json=payload,
            timeout=30,
        )
        if r.status_code == 201:
            return True, "sent(brevo)"
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        return False, f"brevo_{r.status_code}:{str(body.get('message', ''))[:120]}"
    except requests.RequestException as exc:
        return False, f"brevo_network:{type(exc).__name__}"


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
    return _dispatch(to, subject, None, body)


def send_email_html(to: str, subject: str, html: str) -> tuple[bool, str]:
    """Envoie un email HTML. Retourne (envoyé, détail)."""
    return _dispatch(to, subject, html, None)


def _dispatch(to: str, subject: str, html: str | None, text: str | None) -> tuple[bool, str]:
    if not to:
        return False, "recipient_missing"
    via_resend = _send_via_resend(to, subject, html or "", text or "")
    if via_resend is not None:
        return via_resend
    via_brevo = _send_via_brevo(to, subject, html or "", text or "")
    if via_brevo is not None:
        return via_brevo
    if not config.email_ready():
        return False, "email_not_configured"
    if html is not None:
        msg = MIMEText(html, "html", "utf-8")
    else:
        msg = MIMEText(text or "", "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = config.SMTP_FROM
    msg["To"] = to
    return _smtp_send(to, msg)
