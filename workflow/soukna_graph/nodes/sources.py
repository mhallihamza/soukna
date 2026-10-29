# =====================================================================
# Nœud sources : ingestion des opportunités (carte soukna-sources-agent).
# Portail marchespublics.gov.ma si PORTAL_ENABLED, repli seeds sinon.
# Ne s'exécute qu'en mode pipeline (le chat lit les données existantes).
# =====================================================================
from __future__ import annotations

from typing import Any

from .. import config, db
from ..state import AgentState
from ..tools import portal, seed_data
from ..tracing import traced


@traced("sources", lambda r: f"mode={r.get('source_mode')} ingested={r.get('ingested')}")
def sources_node(state: AgentState) -> dict[str, Any]:
    if not state.get("run_pipeline"):
        return {"ingested": 0, "source_mode": "skip"}

    items: list[dict[str, Any]] = []
    mode = "seed"
    if config.PORTAL_ENABLED:
        try:
            items = portal.fetch_consultations()
            mode = "portal"
        except Exception:
            # Timeouts, structure changée, anti-bot : repli seeds (runbook).
            items = []
    if not items:
        items = list(seed_data.SEED_OPPORTUNITIES)
        mode = "seed"

    ingested = 0
    for item in items:
        try:
            if db.upsert_opportunity(**item):
                ingested += 1
        except Exception:
            continue  # une ligne invalide ne bloque pas l'ingestion

    return {"ingested": ingested, "source_mode": mode}
