# =====================================================================
# État partagé du graphe Soukna.
# =====================================================================
from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    # Entrée webhook (chat) OU pipeline interne
    message: str
    sender_phone: str
    sender_name: str
    message_id: str
    run_pipeline: bool          # True => exécution complète (admin /run)

    # Routage
    route: str                  # process_message | duplicate_message | ignored_event | pipeline
    intent: str                 # greeting | opportunities | digest_request | profile_update | other
    language: str
    extracted: dict[str, Any]

    # Observabilité
    request_id: str

    # Données métier circulant entre agents
    ingested: int
    source_mode: str
    source_detail: str             # statut par source (multi-sources)
    history: list[dict[str, Any]]  # mémoire de conversation (chat)
    company: dict[str, Any]     # profil de l'entreprise courante (chat)
    matches: list[dict[str, Any]]
    digest_items: list[dict[str, Any]]
    digest_text: str
    delivered: list[str]

    # FAQ agent (RAG sur Astra souknabase)
    faq_hits: int               # passages de la KB utilisés pour la réponse
    faq_sources: list[str]      # documents consultés (ex. soukna-kb-02-tarifs-fr)
    llm_mode: str               # mistral | heuristic (dernier agent LLM)

    # Sortie
    reply_text: str
    whatsapp_sent: bool | None
    error: str
    agent_timings: list[dict[str, Any]]
    llm_usage: dict[str, int]    # {"in": n, "out": n} cumulés sur la requête
