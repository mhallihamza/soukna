# =====================================================================
# Observabilité : wrapper `traced()` par nœud + finalisation de requête.
# Chaque exécution écrit dans lg_requests (une ligne) et lg_logs (n lignes).
# =====================================================================
from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any

from . import db
from .state import AgentState


def traced(agent: str, detail_fn: Callable[[dict[str, Any]], str] | None = None):
    """Décorateur de nœud : mesure la durée et trace dans lg_logs."""

    def decorator(fn: Callable[[AgentState], dict[str, Any] | Any]):
        @functools.wraps(fn)
        async def wrapper(state: AgentState) -> dict[str, Any]:
            t0 = time.monotonic()
            result = fn(state)
            if hasattr(result, "__await__"):
                result = await result
            duration = time.monotonic() - t0
            detail = ""
            if detail_fn is not None:
                try:
                    detail = detail_fn(dict(result or {}))
                except Exception:
                    detail = ""
            try:
                if state.get("request_id"):
                    timings = [*(state.get("agent_timings") or []),
                               {"agent": agent, "duration_s": round(duration, 3)}]
                    result = {**(result or {}), "agent_timings": timings}
                    db.log_agent(state["request_id"], agent, duration, detail)
            except Exception:
                pass  # l'observabilité ne doit jamais casser le pipeline
            return result

        return wrapper

    return decorator
