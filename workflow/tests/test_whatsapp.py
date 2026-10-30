# =====================================================================
# Canal WhatsApp : détection du rejet silencieux de Meta.
# Meta peut répondre 200 sans wamid (destinataire non vérifié sur un
# numéro de test) — l'envoi doit alors être signalé comme échec.
# =====================================================================
from types import SimpleNamespace

from soukna_graph.tools import whatsapp


def _meta_response(payload: dict, status: int = 200):
    return SimpleNamespace(
        status_code=status,
        headers={"content-type": "application/json"},
        json=lambda: payload,
    )


def _send(monkeypatch, payload: dict):
    monkeypatch.setattr(whatsapp.requests, "post",
                        lambda *a, **k: _meta_response(payload))
    return whatsapp.send_whatsapp("212659865507", "test")


def test_send_ok_with_message_id(monkeypatch):
    ok, detail = _send(monkeypatch, {
        "contacts": [{"input": "212659865507", "wa_id": "212659865507"}],
        "messages": [{"id": "wamid.test123"}],
    })
    assert ok is True and detail == "sent"


def test_silent_rejection_without_message_id(monkeypatch):
    ok, detail = _send(monkeypatch, {"contacts": [], "messages": []})
    assert ok is False and detail == "meta_rejected_silently"


def test_error_body_is_failure(monkeypatch):
    ok, detail = _send(monkeypatch, {
        "error": {"code": 131030, "message": "destinataire hors périmètre"},
    })
    assert ok is False and "131030" in detail
