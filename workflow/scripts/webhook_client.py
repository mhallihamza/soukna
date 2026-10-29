# =====================================================================
# webhook_client.py — exerce le VRAI webhook HTTP (POST /webhook,
# enveloppe Meta). Le serveur doit tourner : uvicorn api:app --port 8000
# =====================================================================
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import TEST_PHONE  # noqa: E402

BASE_URL = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000"


def main() -> None:
    message = sys.argv[1] if len(sys.argv) > 1 else "Bonjour"
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "1",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "contacts": [{"profile": {"name": "Test Soukna"}, "wa_id": TEST_PHONE}],
                    "messages": [{
                        "from": TEST_PHONE,
                        "id": f"wamid.manual-{uuid.uuid4()}",
                        "type": "text",
                        "text": {"body": message},
                    }],
                },
                "field": "messages",
            }],
        }],
    }
    r = requests.post(f"{BASE_URL}/webhook", json=payload, timeout=30)
    print(f"POST {BASE_URL}/webhook -> {r.status_code} {r.text}")
    if r.status_code == 200:
        print("(le graphe s'exécute en arrière-plan ; la réponse part sur")
        print(" WhatsApp si le numéro est whitelisté, sinon kill switch.)")


if __name__ == "__main__":
    main()
