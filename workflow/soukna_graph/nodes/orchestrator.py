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

ALLOWED_INTENTS = {"greeting", "opportunities", "digest_request", "profile_update", "faq", "other"}


def heuristic_intent(message: str) -> dict[str, Any]:
    """Repli sans LLM : mots-clés fr/ar/en, priorité aux intentions utiles."""
    m = (message or "").lower()

    def has(*words: str) -> bool:
        return any(w in m for w in words)

    # Ordre du plus spécifique au plus large ; les salutations restent des
    # salutations même longues (« Salam, comment allez-vous ? » = greeting).
    if has("synth", "digest", "récap", "recap", "résum", "resum", "ملخص"):
        intent = "digest_request"
    elif has("profil", "profile", "sector", "secteur", "région", "region",
             "mot-clé", "mot cle", "ملف", "قطاع"):
        intent = "profile_update"
    elif has("opportunit", "match", "appel", "offre", "marché", "marche",
             "فرص", "صفقة", "مناقصة"):
        intent = "opportunities"
    elif has("bonjour", "salut", "hello", "salam", "سلام", "صباح", "مسا"):
        intent = "greeting"
    # FAQ : questions standards sur Soukna elle-même (tarifs, compte, guide…)
    elif has("comment", "combien", "pourquoi", "est-ce que", "qui sommes",
             "fonctionne", "abonnement", "tarif", "prix", "coût", "cout", "compte",
             "essai", "gratuit", "contact", "support", "aide",
             "how", "what", "price", "cost", "account", "free trial",
             "دعم", "مساعدة", "كيف", "شنو", "واش", "ثمن", "حساب",
             "اشتراك", "أسعار"):
        intent = "faq"
    else:
        intent = "other"
    # Langue : des caractères arabes → ar ; mots anglais explicites → en ; sinon fr.
    if any("\u0600" <= ch <= "\u06FF" for ch in message or ""):
        language = "ar"
    elif has("hello", "what", "how", "price", "help", "opportunities", "summary"):
        language = "en"
    else:
        language = "fr"
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
    language = parsed.get("language") if parsed.get("language") in {"fr", "en", "ar"} \
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
