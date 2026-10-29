# =====================================================================
# chat_interactive.py — chat tapez-et-répondez avec le VRAI graphe.
# Contexte par tour (comme un webhook) ; 'quit' pour sortir.
# =====================================================================
from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import ensure_db, run_graph  # noqa: E402

PHONE = "+212600000001"


async def main() -> None:
    ensure_db()
    print("Chat Soukna (le vrai graphe) — 'quit' pour sortir")
    print("=" * 60)
    while True:
        try:
            message = input("vous  > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not message or message.lower() in {"quit", "exit", "q"}:
            break
        result = await run_graph({
            "message": message,
            "sender_phone": PHONE,
            "sender_name": "Test Soukna",
            "message_id": f"manual-{uuid.uuid4()}",
        })
        print(f"route : {result.get('route')}  |  intent : {result.get('intent')}")
        print("-" * 60)
        print(result.get("reply_text") or "(aucune réponse)")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
