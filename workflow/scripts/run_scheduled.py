# =====================================================================
# run_scheduled.py — pipeline quotidien planifié (GitHub Actions cron).
# Exécute le graphe complet : sources → matching → verdict → digest
# (envois WhatsApp/email réels ; KILL_SWITCH=false est imposé par le job).
#
# Sortie : résumé JSON lisible dans le job + code retour (1 si error).
# =====================================================================
from __future__ import annotations

import json
import sys

sys.path.insert(0, ".")

from soukna_graph.graph import run_pipeline  # noqa: E402
from soukna_graph.state import AgentState  # noqa: E402


def main() -> int:
    result: AgentState = run_pipeline()
    error = result.get("error") or ""
    summary = {
        "source_mode": result.get("source_mode"),
        "ingested": result.get("ingested"),
        "matches": len(result.get("matches") or []),
        "digests": len(result.get("digest_items") or []),
        "delivered": result.get("delivered") or [],
        "error": error or None,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
