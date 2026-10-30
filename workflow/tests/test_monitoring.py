# =====================================================================
# Agent de monitoring : logique des checks, agrégation, alertes.
# 100 % hors-ligne — toute lecture DB (db.request_stats, db.query,
# db.get_state…) est monkeypatchée localement, conformément à conftest.
# =====================================================================
import time

import pytest
from fastapi.testclient import TestClient

from soukna_graph import config, monitoring


# ---------------------------------------------------------------------
# Checks unitaires
# ---------------------------------------------------------------------
def test_error_rate_none_is_ok():
    c = monitoring._check_error_rate(None, 20)
    assert c["status"] == "ok"


def test_error_rate_thresholds():
    c = monitoring._check_error_rate(19.9, 20)
    assert c["status"] == "ok"
    c = monitoring._check_error_rate(25, 20)
    assert c["status"] == "warn"
    c = monitoring._check_error_rate(41, 20)  # >= seuil x2
    assert c["status"] == "crit"


def test_latency_picks_worst_agent():
    agents = [{"agent": "digest", "p95_s": 5.0}, {"agent": "parse", "p95_s": 150.0}]
    c = monitoring._check_latency(agents, 120)
    assert c["status"] == "warn"
    assert c["value"]["agent"] == "parse"
    assert c["value"]["p95_s"] == 150.0


def test_latency_thresholds():
    assert monitoring._check_latency([{"agent": "a", "p95_s": 10}], 120)["status"] == "ok"
    assert monitoring._check_latency([{"agent": "a", "p95_s": 200}], 120)["status"] == "warn"
    assert monitoring._check_latency([{"agent": "a", "p95_s": 240}], 120)["status"] == "crit"
    assert monitoring._check_latency([], 120)["status"] == "ok"


def test_llm_cost_thresholds():
    assert monitoring._check_llm_cost(1.0, 5.0)["status"] == "ok"
    assert monitoring._check_llm_cost(6.0, 5.0)["status"] == "warn"
    assert monitoring._check_llm_cost(11.0, 5.0)["status"] == "crit"


def test_fallback_none_and_over_threshold():
    assert monitoring._check_fallback(None, 50)["status"] == "ok"
    assert monitoring._check_fallback(30, 50)["status"] == "ok"
    assert monitoring._check_fallback(60, 50)["status"] == "warn"
    assert monitoring._check_fallback(90, 50)["status"] == "warn"


def test_staleness_none_is_crit_and_scaling():
    c = monitoring._check_staleness("portal_freshness", "portail", None, 36)
    assert c["status"] == "crit"
    assert monitoring._check_staleness("x", "portail", 10.0, 36)["status"] == "ok"
    assert monitoring._check_staleness("x", "portail", 40.0, 36)["status"] == "warn"
    # >= seuil x2 : critique
    assert monitoring._check_staleness("x", "portail", 80.0, 36)["status"] == "crit"


def test_digest_delivery_no_companies_is_ok():
    c = monitoring._check_digest_delivery([])
    assert c["status"] == "ok"


def test_digest_delivery_all_delivered_is_ok(monkeypatch):
    monkeypatch.setattr(config, "KILL_SWITCH", False)
    rows = [{"name": "A", "channels": ["whatsapp", "email"]}]
    assert monitoring._check_digest_delivery(rows)["status"] == "ok"
    rows = [{"name": "A", "channels": None}]  # pas de digest du tout
    assert monitoring._check_digest_delivery(rows)["status"] == "warn"


def test_digest_delivery_missing_warns(monkeypatch):
    monkeypatch.setattr(config, "KILL_SWITCH", False)
    rows = [{"name": "A", "channels": []}, {"name": "B", "channels": ["whatsapp"]}]
    c = monitoring._check_digest_delivery(rows)
    assert c["status"] == "warn"
    assert c["value"] == ["A"]


def test_digest_delivery_kill_switch_expected(monkeypatch):
    monkeypatch.setattr(config, "KILL_SWITCH", True)
    rows = [{"name": "A", "channels": []}]
    c = monitoring._check_digest_delivery(rows)
    assert c["status"] == "ok"


def test_aggregate_takes_worst_severity():
    assert monitoring._aggregate([{"status": "ok"}, {"status": "ok"}]) == "ok"
    assert monitoring._aggregate([{"status": "ok"}, {"status": "warn"}]) == "warn"
    assert monitoring._aggregate([{"status": "warn"}, {"status": "crit"}]) == "crit"


# ---------------------------------------------------------------------
# run_checks : rapport complet sans DB (collecte monkeypatchée)
# ---------------------------------------------------------------------
@pytest.fixture
def fake_db(monkeypatch):
    """Remplace tous les accès DB du monitoring par des données saines."""
    req = {"total": 10, "errors": 0, "llm_cost_usd": 0.12}
    monkeypatch.setattr(monitoring.db, "request_stats", lambda hours: req)
    monkeypatch.setattr(monitoring.db, "agent_stats",
                        lambda hours: [{"agent": "parse", "p95_s": 3.2}])
    monkeypatch.setattr(monitoring.db, "query", sql_passthrough)
    monkeypatch.setattr(config, "KILL_SWITCH", False)
    monkeypatch.setattr(config, "PORTAL_ENABLED", True)
    monkeypatch.setattr(config, "LLM_ENABLED", True)
    return req


def sql_passthrough(sql, params=()):
    """Réponses saines aux SELECT du monitoring, selon la requête."""
    if "companies_active" in sql:
        return [{"companies_active": 3, "opportunities": 12,
                 "matches_new": 5, "digests_sent": 3}]
    if "route = 'pipeline'" in sql:
        return [{"pipelines": 10, "no_llm": 2}]
    if "MAX(created_at)" in sql:
        return [{"hours": 2.0}]
    if "MAX(started_at)" in sql:
        return [{"hours": 1.0}]
    if "c.name, d.channels" in sql:
        return [{"name": "A", "channels": ["whatsapp"]}]
    raise AssertionError(f"requête inattendue : {sql[:80]}")


def test_run_checks_healthy_report(fake_db):
    report = monitoring.run_checks()
    assert report["status"] == "ok"
    ids = [c["id"] for c in report["checks"]]
    assert ids == ["error_rate", "latency", "llm_cost", "llm_fallback",
                   "portal_freshness", "pipeline_freshness", "digest_whatsapp"]
    assert report["stats"]["companies_active"] == 3
    assert "kill_switch" in report["config"]


def test_run_checks_db_down_returns_crit_without_raising(fake_db, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("connexion perdue")
    monkeypatch.setattr(monitoring.db, "request_stats", boom)
    report = monitoring.run_checks()
    assert report["status"] == "crit"
    assert report["checks"][0]["id"] == "db_connectivity"


# ---------------------------------------------------------------------
# maybe_alert : anti-spam et canaux
# ---------------------------------------------------------------------
@pytest.fixture
def no_channels(monkeypatch):
    """Neutralise l'état persistant et les canaux d'alerte."""
    monkeypatch.setattr(monitoring.db, "get_state", lambda key: None)
    monkeypatch.setattr(monitoring.db, "set_state", lambda key, value: None)
    monkeypatch.setattr(monitoring.emailer, "send_email_html",
                        lambda to, subject, html: (True, "ok"))
    monkeypatch.setattr(monitoring.whatsapp, "send_whatsapp",
                        lambda to, text: (True, "ok"))
    monkeypatch.setattr(config, "MON_ALERT_WHATSAPP", "")
    monkeypatch.setattr(config, "ADMIN_USERNAME", "admin@soukna.ma")


def _degraded_report():
    return {"status": "warn", "window_hours": 24, "checks": [
        {"id": "error_rate", "status": "warn", "value": 25, "detail": "25%"},
        {"id": "latency", "status": "ok", "value": None, "detail": ""},
    ]}


def test_alert_first_degradation_sends_email(no_channels):
    out = monitoring.maybe_alert(_degraded_report())
    assert out["sent"] == ["email:admin@soukna.ma"]
    assert out["degraded"] == ["error_rate"]


def test_alert_healthy_resets_state(no_channels, monkeypatch):
    saved = {}
    monkeypatch.setattr(monitoring.db, "set_state",
                        lambda key, value: saved.setdefault(key, value))
    out = monitoring.maybe_alert({"status": "ok", "checks": [], "window_hours": 24})
    assert out["sent"] == []
    assert saved["monitoring_alert"]["degraded"] == []


def test_alert_same_degradation_within_cooldown_is_silent(no_channels, monkeypatch):
    monkeypatch.setattr(monitoring.db, "get_state", lambda key: {
        "degraded": ["error_rate"], "ts": time.time(), "status": "warn"})
    out = monitoring.maybe_alert(_degraded_report())
    assert out["sent"] == []
    assert "cooldown" in out["reason"]


def test_alert_new_degradation_set_sends_again(no_channels, monkeypatch):
    monkeypatch.setattr(monitoring.db, "get_state", lambda key: {
        "degraded": ["latency"], "ts": time.time(), "status": "warn"})
    out = monitoring.maybe_alert(_degraded_report())
    assert out["sent"] == ["email:admin@soukna.ma"]


def test_alert_after_cooldown_sends_again(no_channels, monkeypatch):
    old = time.time() - config.MON_ALERT_COOLDOWN_H * 3600 - 1
    monkeypatch.setattr(monitoring.db, "get_state", lambda key: {
        "degraded": ["error_rate"], "ts": old, "status": "warn"})
    assert monitoring.maybe_alert(_degraded_report())["sent"]


def test_alert_email_failure_does_not_raise(no_channels, monkeypatch):
    monkeypatch.setattr(monitoring.emailer, "send_email_html",
                        lambda to, subject, html: (False, "SMTP indisponible"))
    out = monitoring.maybe_alert(_degraded_report())
    assert out["sent"] == ["email:échec (SMTP indisponible)"]


def test_alert_whatsapp_channel_optional(no_channels, monkeypatch):
    monkeypatch.setattr(config, "MON_ALERT_WHATSAPP", "212600000000")
    out = monitoring.maybe_alert(_degraded_report())
    assert "whatsapp:envoyé" in out["sent"]


def test_alert_text_and_html_contain_degraded_checks():
    report = _degraded_report()
    text = monitoring._alert_text(report, ["error_rate"])
    assert "MONITORING" in text.upper()
    assert "error_rate : 25%" in text
    html = monitoring._alert_html(report, ["error_rate"])
    assert "error_rate" in html and "WARN" in html


# ---------------------------------------------------------------------
# Endpoint API : authentification admin requise
# ---------------------------------------------------------------------
def test_monitoring_endpoint_requires_admin():
    from api import app
    client = TestClient(app)
    assert client.get("/monitoring/report").status_code == 401
