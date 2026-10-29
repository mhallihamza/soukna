# =====================================================================
# Mémoire de conversation par expéditeur (entre deux messages webhook).
# Même principe que le projet clinique : TTL 30 min, stockage process.
# =====================================================================
from __future__ import annotations

import time
from typing import Any

TTL_S = 30 * 60

_STORE: dict[str, dict[str, Any]] = {}


def save(phone: str, final_state: dict[str, Any]) -> None:
    if not phone:
        return
    _STORE[phone] = {
        "intent": final_state.get("intent"),
        "language": final_state.get("language"),
        "extracted": final_state.get("extracted") or {},
        "reply_text": final_state.get("reply_text", ""),
        "at": time.monotonic(),
    }


def get(phone: str) -> dict[str, Any] | None:
    ctx = _STORE.get(phone or "")
    if not ctx or time.monotonic() - ctx["at"] > TTL_S:
        return None
    return ctx


def clear(phone: str) -> None:
    _STORE.pop(phone or "", None)
