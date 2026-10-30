# =====================================================================
# Graphe Soukna — 8 nœuds, deux modes d'exécution :
#   • pipeline (admin /run ou cron) :
#       intake → sources → matching → verdict → digest → END
#   • chat (webhook WhatsApp) :
#       intake → orchestrator → (matching → verdict → digest)? → response
#                          ou faq → response (questions standards, RAG Astra)
# =====================================================================
from __future__ import annotations

import asyncio
import uuid
from typing import Any

from langgraph.graph import END, StateGraph

from .nodes.digest import digest_node
from .nodes.faq import faq_node
from .nodes.intake import intake_node
from .nodes.matching import matching_node
from .nodes.orchestrator import orchestrator_node
from .nodes.response import response_node
from .nodes.sources import sources_node
from .nodes.verdict import verdict_node
from .state import AgentState


def _route_from_intake(state: AgentState) -> str:
    route = state.get("route")
    if route == "pipeline":
        return "pipeline"
    if route == "process_message":
        return "orchestrator"
    return "end"  # duplicate_message / ignored_event : aucun agent


def _route_from_orchestrator(state: AgentState) -> str:
    if state.get("intent") in {"opportunities", "digest_request"}:
        return "matching"
    if state.get("intent") == "faq":
        return "faq"
    return "response"


def _after_digest(state: AgentState) -> str:
    return "end" if state.get("run_pipeline") else "response"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("intake", intake_node)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("sources", sources_node)
    graph.add_node("matching", matching_node)
    graph.add_node("verdict", verdict_node)
    graph.add_node("digest", digest_node)
    graph.add_node("faq", faq_node)
    graph.add_node("response", response_node)

    graph.set_entry_point("intake")
    graph.add_conditional_edges("intake", _route_from_intake, {
        "pipeline": "sources",
        "orchestrator": "orchestrator",
        "end": END,
    })
    graph.add_edge("sources", "matching")
    graph.add_edge("matching", "verdict")
    graph.add_edge("verdict", "digest")
    graph.add_conditional_edges("digest", _after_digest, {
        "response": "response",
        "end": END,
    })
    graph.add_conditional_edges("orchestrator", _route_from_orchestrator, {
        "matching": "matching",
        "faq": "faq",
        "response": "response",
    })
    graph.add_edge("faq", "response")
    return graph.compile()


def run_pipeline() -> dict[str, Any]:
    """Exécute le pipeline complet (API admin, cron du digest)."""
    graph = build_graph()
    return asyncio.run(graph.ainvoke({
        "run_pipeline": True,
        "sender_phone": "system",
        "message_id": f"pipeline-{uuid.uuid4()}",
    }))
