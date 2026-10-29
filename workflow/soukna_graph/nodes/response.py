# =====================================================================
# Nœud response : rédige la réponse finale du chat et l'envoie sur le
# canal d'origine (WhatsApp). Le kill switch s'applique dans l'outil.
# =====================================================================
from __future__ import annotations

from typing import Any

from .. import db
from ..state import AgentState
from ..tools.whatsapp import send_whatsapp
from ..tracing import traced

GREETING_TEXT = (
    "Bonjour 👋 Bienvenue sur Soukna, votre veille des marchés publics.\n\n"
    "Je peux vous aider à tout moment :\n"
    "• « opportunités » — les appels d'offres matchés avec votre profil\n"
    "• « synthèse » — votre récapitulatif du jour\n"
    "• « profil » — ajuster secteur, régions, mots-clés\n\n"
    "Analyse indicative — le dossier officiel fait toujours foi."
)

FALLBACK_TEXT = (
    "Je suis l'assistant Soukna 🤖 Voici ce que je sais faire :\n"
    "• « opportunités » — voir les appels d'offres qui correspondent à votre profil\n"
    "• « synthèse » — recevoir votre récapitulatif\n"
    "• « profil » — ajuster vos préférences\n\n"
    "Pour une gestion complète, ouvrez votre dashboard Soukna."
)

PROFILE_HOWTO_TEXT = (
    "Pour ajuster votre profil, indiquez par exemple :\n"
    "« secteur : Informatique, région : Casablanca »\n\n"
    "Vous pouvez aussi tout gérer depuis votre dashboard Soukna."
)

PROFILE_UPDATED_TEXT = "✅ Profil mis à jour. Vos prochaines synthèses en tiendront compte."


def _as_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _apply_profile_update(company: dict[str, Any] | None, extracted: dict[str, Any]) -> bool:
    """Applique sector/région/mots-clés extraits du message, si présents."""
    if not company:
        return False
    sectors = _as_list(extracted.get("sector"))
    regions = _as_list(extracted.get("region"))
    keywords = _as_list(extracted.get("keywords"))
    if not (sectors or regions or keywords):
        return False
    db.update_company_profile(
        str(company["id"]),
        sectors=sectors or None,
        keywords=keywords or None,
        regions=regions or None,
    )
    return True


@traced("response", lambda r: f"whatsapp={r.get('whatsapp_sent')}")
def response_node(state: AgentState) -> dict[str, Any]:
    intent = state.get("intent", "other")
    company = state.get("company")

    if intent in {"opportunities", "digest_request"}:
        reply = state.get("digest_text") or FALLBACK_TEXT
    elif intent == "greeting":
        reply = GREETING_TEXT
    elif intent == "profile_update":
        applied = _apply_profile_update(company, state.get("extracted") or {})
        reply = PROFILE_UPDATED_TEXT if applied else PROFILE_HOWTO_TEXT
    else:
        reply = FALLBACK_TEXT

    whatsapp_sent: bool | None = None
    phone = state.get("sender_phone") or ""
    if phone and phone != "system":
        whatsapp_sent, _detail = send_whatsapp(phone, reply)

    return {"reply_text": reply, "whatsapp_sent": whatsapp_sent}
