# =====================================================================
# Nœud faq : répond aux questions standards (tarifs, compte, guide…)
# à partir de la base de connaissances Astra (souknabase).
#
# 1) recherche vectorielle $vectorize (embedding NVIDIA intégré Astra)
# 2) réponse rédigée par le LLM UNIQUEMENT à partir des passages trouvés
#    (RAG strict : pas d'invention, renvoi vers le support si insuffisant)
# 3) repli heuristique sans LLM : extrait du meilleur passage + sources
# =====================================================================
from __future__ import annotations

import re
from typing import Any

from .. import config
from ..llm import extract_usage, make_llm, merge_usage
from ..state import AgentState
from ..tools import astra_kb
from ..tracing import traced

# Dernier recours : quand la KB est vide ou injoignable, on ne prétend
# rien : on redirige vers le dashboard et le support.
FAQ_FALLBACK_TEXT = {
    "fr": "Je n'ai pas trouvé de réponse fiable à votre question dans ma "
          "documentation. Précisez-la ou contactez le support depuis votre "
          "dashboard Soukna.",
    "en": "I couldn't find a reliable answer to your question in my "
          "documentation. Please rephrase it or contact support from your "
          "Soukna dashboard.",
    "ar": "لم أجد إجابة موثوقة لسؤالك في وثائقي. أعد صياغته أو تواصل مع "
          "الدعم من لوحة سوكنا.",
}


def detect_language(message: str) -> str | None:
    """Détection d'arabe indépendante du LLM (documents bilingues fr/ar)."""
    return "ar" if re.search(r"[\u0600-\u06FF]", message or "") else None


def _build_prompt(question: str, context: str, language: str) -> str:
    return (
        "Tu es l'agent FAQ de Soukna, plateforme marocaine de veille des "
        "marchés publics. Tu réponds aux questions standards des entreprises "
        "(présentation, tarifs, compte, matching, guide d'utilisation, "
        "données, contact) en t'appuyant EXCLUSIVEMENT sur les EXTRATS "
        "ci-dessous de notre base de connaissances.\n\n"
        "RÈGLES :\n"
        "- Réponds dans la langue de la question indiquée ci-dessous.\n"
        "- Si les extrats ne suffisent pas, dis-le et invite "
        "à consulter le dashboard Soukna ou le support — n'invente rien.\n"
        "- Ton professionnel et concis (souple, listes courtes si utile).\n"
        f"- Longueur : {config.FAQ_MAX_ANSWER_CHARS} caractères maximum.\n\n"
        "EXTRATS DE LA BASE DE CONNAISSANCES :\n"
        f"{context}\n\n"
        f"LANGUE ATTENDUE : {language}\n"
        f"QUESTION : {question}\n\n"
        "Réponds directement en texte, sans balise JSON."
    )


def _fallback_from_hits(hits: list[dict], language: str) -> str:
    """Sans LLM : extrait condensé du meilleur passage + sources consultées."""
    if not hits:
        return FAQ_FALLBACK_TEXT.get(language or "fr", FAQ_FALLBACK_TEXT["fr"])
    top = hits[0]
    body = re.sub(r"\s+", " ", top["text"]).strip()
    if len(body) > 320:
        body = body[:317].rstrip() + "…"
    sources = ", ".join(dict.fromkeys(h["doc"] for h in hits if h["doc"]))
    return f"{body}\n\n(de : {sources})"


@traced("faq", lambda r: f"hits={r.get('faq_hits')} llm={r.get('llm_mode', '')}")
def faq_node(state: AgentState) -> dict[str, Any]:
    question = state.get("message") or ""
    language = state.get("language") or "fr"
    if not state.get("language"):
        # le chat peut arriver sans classification : l'arabe est prioritaire
        language = detect_language(question) or "fr"

    hits: list[dict] = []
    try:
        hits = astra_kb.search(question, lang=language)
        context = astra_kb.format_context(hits)
    except Exception:  # Astra injoignable : l'agent FAQ ne plante jamais le chat
        hits, context = [], ""

    result: dict[str, Any] = {
        "faq_hits": len(hits),
        "faq_sources": sorted({h["doc"] for h in hits if h["doc"]}),
    }

    if not hits:
        result["reply_text"] = FAQ_FALLBACK_TEXT.get(language, FAQ_FALLBACK_TEXT["fr"])
        return result

    llm, llm_mode = make_llm()
    if llm is None or not context:
        result["reply_text"] = _fallback_from_hits(hits, language)
        return result

    try:
        resp = llm.invoke(_build_prompt(question, context, language))
        answer = (getattr(resp, "content", "") or "").strip()
        if not answer:
            raise ValueError("réponse LLM vide")
        if len(answer) > config.FAQ_MAX_ANSWER_CHARS:
            answer = answer[:config.FAQ_MAX_ANSWER_CHARS].rstrip()
        result["reply_text"] = answer
        result["llm_mode"] = llm_mode
        result["llm_usage"] = merge_usage(state, extract_usage(resp))
    except Exception:
        result["reply_text"] = _fallback_from_hits(hits, language)
        result["llm_mode"] = "heuristic"
    return result
