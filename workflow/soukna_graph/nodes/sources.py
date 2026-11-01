# =====================================================================
# Nœud sources : ingestion MULTI-SOURCES (carte soukna-sources-agent).
# Itère le registre `sources` de la base (console admin : activer/
# désactiver, cadence) et dispatch vers l'adaptateur de chaque source.
# Un échec de source n'empêche pas les autres (statut tracé par source).
# Repli seeds si AUCUNE source ne répond. Mode pipeline uniquement.
# =====================================================================
from __future__ import annotations

from typing import Any

from .. import config, db
from ..state import AgentState
from ..tools import seed_data
from ..tools.scrapers import get_adapter
from ..tracing import traced


@traced("sources", lambda r: f"mode={r.get('source_mode')} ingested={r.get('ingested')}")
def sources_node(state: AgentState) -> dict[str, Any]:
    if not state.get("run_pipeline"):
        return {"ingested": 0, "source_mode": "skip"}

    items: list[dict[str, Any]] = []
    per_source: list[str] = []
    sources = db.sources_list(enabled_only=True)
    mode = "seed"

    for src in sources:
        adapter = get_adapter(src.get("adapter", ""))
        if adapter is None:
            status = f"unknown_adapter:{src.get('adapter', '')}"
            db.sources_update_status(str(src["id"]), status)
            per_source.append(f"{src['name']}:{status}")
            continue
        try:
            fetched = adapter(dict(src)) or []
        except Exception as exc:  # timeout, structure changée, anti-bot…
            status = f"failed {type(exc).__name__}: {str(exc)[:120]}"
            db.sources_update_status(str(src["id"]), status)
            per_source.append(f"{src['name']}:failed")
            continue
        items.extend(fetched)
        status = f"ok items={len(fetched)}"
        db.sources_update_status(str(src["id"]), status)
        per_source.append(f"{src['name']}:{len(fetched)}")

    if not sources and config.PORTAL_ENABLED:
        # Registre vide (avant configuration admin) : comportement
        # historique = portail national direct.
        try:
            adapter = get_adapter("marchespublics")
            items = adapter({"name": "portal"}) or []
            mode = "portal"
            per_source.append("portal(legacy):" + str(len(items)))
        except Exception:
            per_source.append("portal(legacy):failed")

    if items:
        mode = "multi" if len(sources) > 1 else (sources[0]["adapter"] if sources else mode)

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

    return {
        "ingested": ingested,
        "source_mode": mode,
        "source_detail": " | ".join(per_source)[:500],
    }
