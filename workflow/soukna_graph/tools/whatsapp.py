# =====================================================================
# Canal WhatsApp (Cloud API Meta) — kill switch + liste blanche de test.
# Même contrat que le projet clinique : HTTP 200 avec corps d'erreur Meta
# est traité comme un échec (error 131030 = destinataire hors périmètre).
# =====================================================================
from __future__ import annotations

import requests

from .. import config


def send_whatsapp(phone: str, text: str) -> tuple[bool, str]:
    """Envoie un message. Retourne (envoyé, détail).

    Kill switch actif : seul un numéro de WHATSAPP_TEST_RECIPIENTS reçoit
    un vrai message ; tout autre envoi est silencieusement neutralisé
    (traçabilité : 'kill_switch_active').
    """
    if not (config.WHATSAPP_TOKEN and config.WHATSAPP_PHONE_NUMBER_ID):
        return False, "whatsapp_not_configured"
    if config.KILL_SWITCH and not config.is_test_recipient(phone):
        return False, "kill_switch_active"

    url = f"{config.WHATSAPP_API}/{config.WHATSAPP_PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": "".join(ch for ch in phone if ch.isdigit()),
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }
    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {config.WHATSAPP_TOKEN}"},
            json=payload,
            timeout=30,
        )
        # Meta répond parfois 200 avec un corps d'erreur : à traiter.
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code == 200 and not body.get("error"):
            # 200 SANS wamid (contacts/messages vides) = rejet silencieux :
            # typiquement un destinataire non vérifié sur le numéro de test.
            if not (body.get("messages") or []):
                return False, "meta_rejected_silently"
            return True, "sent"
        err = body.get("error") or {}
        return False, f"meta_{err.get('code', r.status_code)}:{str(err.get('message', ''))[:120]}"
    except requests.RequestException as exc:
        return False, f"network:{type(exc).__name__}"
