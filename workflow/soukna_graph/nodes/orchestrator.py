# =====================================================================
# Nœud orchestrator : classification de l'intention (LLM + repli
# heuristique déterministe) + résolution de l'entreprise par téléphone.
# =====================================================================
from __future__ import annotations

from typing import Any

from .. import db
from ..llm import call_llm_json, make_llm, merge_usage
from ..prompts import ORCHESTRATOR_SYSTEM, today_hint
from ..state import AgentState
from ..tracing import traced

ALLOWED_INTENTS = {"greeting", "opportunities", "digest_request", "profile_update", "other"}


def heuristic_intent(message: str) -> dict[str, Any]:
    """Repli sans LLM : mots-clés fr/ar/en, priorité aux intentions utiles."""
    m = (message or "").lower()

    def has(*words: str) -> bool:
        return any(w in m for w in words)

    if has("synth", "digest", "récap", "recap", "résum", "resum", "ملخص"):
        intent = "digest_request"
    elif has("profil", "profile", "secteur", "région", "region", "mot-clé",
             "mot cle", "ملف", "قطاع"):
        intent = "profile_update"
    elif has("opportunit", "match", "appel", "offre", "marché", "marche",
             "فرص", "صفقة", "مناقصة"):
        intent = "opportunities"
    elif has("bonjour", "salut", "hello", "salam", "سلام", "صباح", "مسا"):
        intent = "greeting"
    else:
        intent = "other"
    language = "en" if has("hello", "opportunities", "summary") and not has("bonjour") else "fr"
    return {"intent": intent, "language": language, "extracted": {}}


@traced("orchestrator", lambda r: f"intent={r.get('intent')}")
def orchestrator_node(state: AgentState) -> dict[str, Any]:
    message = state.get("message") or ""
    fallback = heuristic_intent(message)

    llm, _mode = make_llm()
    prompt = ORCHESTRATOR_SYSTEM + today_hint() + f"\n\nMESSAGE : {message!r}"
    parsed, _used, usage = call_llm_json(llm, prompt, fallback)

    intent = parsed.get("intent")
    if intent not in ALLOWED_INTENTS:
        intent = fallback["intent"]  # garde-fou : jamais d'intention inconnue
    language = parsed.get("language") if parsed.get("language") in {"fr", "en"} \
        else fallback["language"]
    extracted = parsed.get("extracted") if isinstance(parsed.get("extracted"), dict) else {}

    company = None
    phone = state.get("sender_phone") or ""
    if phone and phone != "system":
        company = db.get_company_by_phone(phone)

    return {
        "intent": intent,
        "language": language,
        "extracted": extracted or {},
        "company": company,
        "llm_usage": merge_usage(state, usage),
    }
