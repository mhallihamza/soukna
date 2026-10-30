# =====================================================================
# API hors-ligne : health, vérification webhook Meta, payload vide.
# Aucune base de données requise (startup tolère l'absence de DB).
# =====================================================================
from fastapi.testclient import TestClient

from api import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_webhook_verify_wrong_token():
    r = client.get("/webhook", params={
        "hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "123456",
    })
    assert r.status_code == 403


def test_webhook_verify_ok():
    from soukna_graph import config
    r = client.get("/webhook", params={
        "hub.mode": "subscribe",
        "hub.verify_token": config.WHATSAPP_VERIFY_TOKEN,
        "hub.challenge": "123456",
    })
    assert r.status_code == 200
    assert r.json() == 123456


def test_webhook_post_empty_entry():
    r = client.post("/webhook", json={"object": "whatsapp_business_account", "entry": []})
    assert r.status_code == 200
    assert r.json() == {"received": True}


def test_webhook_post_non_text_message_ignored():
    # Accusé de réception / statut : aucun traitement, pas de DB
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {"messages": [{"id": "wamid.x", "from": "212600000000"}]}}],
                   "id": "1"}],
    }
    r = client.post("/webhook", json=payload)
    assert r.status_code == 200


def test_auth_required_on_admin_endpoints():
    assert client.get("/stats").status_code == 401
    assert client.get("/observability").status_code == 401
    assert client.post("/run").status_code == 401


def test_login_invalid(monkeypatch):
    # Hors-ligne : on neutralise les deux lectures DB du login (users,
    # companies). Le repli admin .env ne matche pas ("wrong" != mdp).
    monkeypatch.setattr("api.db.get_user_by_email", lambda email: None)
    monkeypatch.setattr("api.db.query", lambda sql, params=(): [])
    r = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401
