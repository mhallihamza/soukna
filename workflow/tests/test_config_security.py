# =====================================================================
# Config & sécurité : kill switch, liste blanche, seuils.
# =====================================================================
from soukna_graph import config
from soukna_graph.tools.whatsapp import send_whatsapp


def test_is_test_recipient_tolerant():
    config.TEST_RECIPIENTS.add("212600000000")
    try:
        assert config.is_test_recipient("+212 600 000 000")
        assert config.is_test_recipient("212600000000")
        assert not config.is_test_recipient("+212 611 111 111")
        assert not config.is_test_recipient("")
    finally:
        config.TEST_RECIPIENTS.discard("212600000000")


def test_send_whatsapp_not_configured(monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_TOKEN", "")
    sent, detail = send_whatsapp("+212600000000", "test")
    assert sent is False
    assert detail == "whatsapp_not_configured"


def test_send_whatsapp_kill_switch_blocks_non_whitelist(monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_TOKEN", "fake-token")
    monkeypatch.setattr(config, "WHATSAPP_PHONE_NUMBER_ID", "123")
    monkeypatch.setattr(config, "KILL_SWITCH", True)
    sent, detail = send_whatsapp("+212611111111", "test")
    assert sent is False
    assert detail == "kill_switch_active"


def test_send_whatsapp_kill_switch_allows_whitelist(monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_TOKEN", "fake-token")
    monkeypatch.setattr(config, "WHATSAPP_PHONE_NUMBER_ID", "123")
    monkeypatch.setattr(config, "KILL_SWITCH", True)
    monkeypatch.setattr(config, "TEST_RECIPIENTS", {"212600000000"})

    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(url)
        return type("R", (), {"status_code": 200, "headers": {"content-type": "application/json"},
                              "json": lambda self: {"messages": [{"id": "wamid.x"}]}})()

    import soukna_graph.tools.whatsapp as wa
    monkeypatch.setattr(wa.requests, "post", fake_post)
    sent, detail = send_whatsapp("+212 600 000 000", "test")
    assert sent is True
    assert detail == "sent"
    assert len(calls) == 1


def test_verdict_thresholds_documented():
    assert config.VERDICT_GO_MIN == 75
    assert config.VERDICT_NOGO_MAX == 45
