# =====================================================================
# send_one.py — envoie UN message à travers le VRAI graphe (en process)
# et affiche la réponse. Usage : python scripts/send_one.py "Bonjour"
# =====================================================================
from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import ensure_db, run_graph  # noqa: E402


async def main() -> None:
    message = " ".join(sys.argv[1:]).strip() or "Bonjour"
    ensure_db()
    state = {
        "message": message,
        "sender_phone": "+212600000001",
        "sender_name": "Test Soukna",
        "message_id": f"manual-{uuid.uuid4()}",
    }
    result = await run_graph(state)
    print(f"route      : {result.get('route')}")
    print(f"intent     : {result.get('intent')}")
    print(f"whatsapp   : {result.get('whatsapp_sent')}")
    print("-" * 60)
    print(result.get("reply_text") or "(aucune réponse)")


if __name__ == "__main__":
    asyncio.run(main())
