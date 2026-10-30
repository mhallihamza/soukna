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
    company: dict[str, Any]     # profil de l'entreprise courante (chat)
    matches: list[dict[str, Any]]
    digest_items: list[dict[str, Any]]
    digest_text: str
    delivered: list[str]

    # Sortie
    reply_text: str
    whatsapp_sent: bool | None
    error: str
    agent_timings: list[dict[str, Any]]
    llm_usage: dict[str, int]    # {"in": n, "out": n} cumulés sur la requête
