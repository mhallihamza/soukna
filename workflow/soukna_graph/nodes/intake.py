# =====================================================================
# Nœud intake : porte d'entrée (carte supervisor-agent-card).
# - pipeline (admin /run) : crée la requête d'observabilité et route.
# - chat : ignore les événements vides, garantit l'idempotence par
#   message_id (un doublon ne déclenche AUCUN agent).
# =====================================================================
from __future__ import annotations

import uuid
from typing import Any

from .. import db
from ..state import AgentState
from ..tracing import traced


@traced("intake", lambda r: f"route={r.get('route')}")
def intake_node(state: AgentState) -> dict[str, Any]:
    if state.get("run_pipeline"):
        message_id = state.get("message_id") or f"pipeline-{uuid.uuid4()}"
        request_id = db.start_request(message_id, state.get("sender_phone") or "system")
        return {"route": "pipeline", "request_id": request_id, "message_id": message_id}

    message = (state.get("message") or "").strip()
    if not message:
        # Accusés de réception Meta, statuts, messages vides : rien à faire.
        return {"route": "ignored_event"}

    message_id = state.get("message_id") or ""
    if message_id:
        if not db.mark_seen(message_id):
            return {"route": "duplicate_message"}
    else:
        # Mode dégradé (carte supervisor) : déduplication neutralisée.
        message_id = f"noid-{uuid.uuid4()}"

    request_id = db.start_request(message_id, state.get("sender_phone") or "")
    return {"route": "process_message", "request_id": request_id, "message_id": message_id}
