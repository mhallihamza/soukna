# =====================================================================
# Agent de monitoring — observe toute la plateforme et alerte.
# Ne fait pas partie du graphe de chat : exécuté par l'API
# (GET /monitoring/report) ou en tâche planifiée (scripts/monitor.py).
#
# Signaux surveillés : disponibilité DB, taux d'erreur des requêtes,
# latence p95 par agent, coût LLM, repli heuristique (LLM dégradé),
# fraîcheur du portail et du pipeline, livraisons WhatsApp du digest.
#
# Sévérités : ok < warn < crit. L'agent ne lève jamais d'exception :
# une surveillance qui plante ne protège rien.
# =====================================================================
from __future__ import annotations

import time
from typing import Any

from . import config, db
from .tools import emailer, whatsapp

OK, WARN, CRIT = "ok", "warn", "crit"
_SEVERITY = {OK: 0, WARN: 1, CRIT: 2}

STATE_KEY = "monitoring_alert"


def _check(cid: str, status: str, value: Any, detail: str) -> dict[str, Any]:
    return {"id": cid, "status": status, "value": value, "detail": detail}


def _check_error_rate(pct: float | None, max_pct: float) -> dict[str, Any]:
    if pct is None:
        return _check("error_rate", OK, None, "aucune requête sur la fenêtre")
    status = CRIT if pct >= max_pct * 2 else (WARN if pct >= max_pct else OK)
    return _check("error_rate", status, round(pct, 1),
                  f"{pct:.1f}% de requêtes en erreur (seuil {max_pct:.0f}%)")


def _check_latency(agents: list[dict[str, Any]], max_p95: float) -> dict[str, Any]:
    if not agents:
        return _check("latency", OK, None, "aucun agent exécuté sur la fenêtre")
    worst = max(agents, key=lambda a: float(a.get("p95_s") or 0))
    p95 = float(worst.get("p95_s") or 0)
    status = CRIT if p95 >= max_p95 * 2 else (WARN if p95 >= max_p95 else OK)
    detail = f"p95 le plus lent : {worst['agent']} à {p95:.1f}s (seuil {max_p95:.0f}s)"
    return _check("latency", status, {"agent": worst["agent"], "p95_s": p95}, detail)


def _check_llm_cost(cost: float, max_cost: float) -> dict[str, Any]:
    status = CRIT if cost >= max_cost * 2 else (WARN if cost >= max_cost else OK)
    return _check("llm_cost", status, round(cost, 4),
                  f"coût LLM {cost:.4f}$ sur la fenêtre (budget {max_cost:.2f}$)")


def _check_fallback(pct: float | None, max_pct: float) -> dict[str, Any]:
    if pct is None:
        return _check("llm_fallback", OK, None, "aucun pipeline sur la fenêtre")
    status = WARN if pct > max_pct else OK
    detail = (f"{pct:.0f}% des pipelines sans appel LLM (seuil {max_pct:.0f}%)"
              if status != OK else f"{pct:.0f}% des pipelines sans appel LLM")
    return _check("llm_fallback", status, round(pct), detail)


def _check_staleness(cid: str, label: str, hours: float | None,
                     max_hours: float) -> dict[str, Any]:
    if hours is None:
        return _check(cid, CRIT, None, f"aucune donnée {label} — vérifier la source")
    status = CRIT if hours >= max_hours * 2 else (WARN if hours >= max_hours else OK)
    return _check(cid, status, round(hours, 1),
                  f"dernière donnée {label} il y a {hours:.1f}h (max {max_hours:.0f}h)")


def _check_digest_delivery(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return _check("digest_whatsapp", OK, None,
                      "aucune entreprise WhatsApp active à surveiller")
    missing = [r["name"] for r in rows
               if "whatsapp" not in (r.get("channels") or [])]
    if not missing:
        return _check("digest_whatsapp", OK, 0,
                      "toutes les entreprises WhatsApp actives ont reçu leur digest")
    if config.KILL_SWITCH:
        return _check("digest_whatsapp", OK, len(missing),
                      f"{len(missing)} sans WhatsApp mais kill switch actif "
                      "(blocage attendu)")
    return _check("digest_whatsapp", WARN, missing,
                  f"digest sans WhatsApp : {', '.join(missing[:5])}")


def _aggregate(checks: list[dict[str, Any]]) -> str:
    worst = OK
    for c in checks:
        if _SEVERITY.get(c["status"], 0) > _SEVERITY[worst]:
            worst = c["status"]
    return worst


def run_checks() -> dict[str, Any]:
    """Exécute tous les checks et retourne le rapport complet."""
    hours = config.MON_WINDOW_H
    try:
        checks, stats = _collect(hours)
    except Exception as exc:
        return {
            "status": CRIT,
            "generated_at": _now(),
            "window_hours": hours,
            "checks": [_check("db_connectivity", CRIT, None,
                              f"base injoignable : {type(exc).__name__}")],
            "stats": {},
            "config": _config_snapshot(),
        }
    return {
        "status": _aggregate(checks),
        "generated_at": _now(),
        "window_hours": hours,
        "checks": checks,
        "stats": stats,
        "config": _config_snapshot(),
    }


def _collect(hours: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    req = db.request_stats(hours)
    total = int(req.get("total") or 0)
    err_rate = (float(req.get("errors") or 0) / total * 100) if total else None
    checks.append(_check_error_rate(err_rate, config.MON_MAX_ERROR_RATE))
    checks.append(_check_latency(db.agent_stats(hours), config.MON_MAX_P95_S))
    checks.append(_check_llm_cost(float(req.get("llm_cost_usd") or 0),
                                  config.MON_MAX_DAILY_COST_USD))

    if config.LLM_ENABLED:
        fb = db.query(
            """
            SELECT count(*) FILTER (WHERE route = 'pipeline') AS pipelines,
                   count(*) FILTER (WHERE route = 'pipeline' AND tokens_in = 0) AS no_llm
            FROM lg_requests
            WHERE started_at > now() - %s * INTERVAL '1 hour'
            """, (hours,))[0]
        pipelines = int(fb.get("pipelines") or 0)
        pct = (float(fb.get("no_llm") or 0) / pipelines * 100) if pipelines else None
        checks.append(_check_fallback(pct, config.MON_MAX_FALLBACK_PCT))

    if config.PORTAL_ENABLED:
        row = db.query(
            "SELECT EXTRACT(EPOCH FROM (now() - MAX(created_at))) / 3600.0 AS hours "
            "FROM opportunities")[0]
        checks.append(_check_staleness(
            "portal_freshness", "portail",
            float(row["hours"]) if row["hours"] is not None else None,
            config.MON_MAX_PORTAL_STALENESS_H))

    row = db.query(
        "SELECT EXTRACT(EPOCH FROM (now() - MAX(started_at))) / 3600.0 AS hours "
        "FROM lg_requests")[0]
    checks.append(_check_staleness(
        "pipeline_freshness", "pipeline",
        float(row["hours"]) if row["hours"] is not None else None,
        config.MON_MAX_PIPELINE_STALENESS_H))

    checks.append(_check_digest_delivery(db.query(
        """
        SELECT c.name, d.channels
        FROM companies c
        JOIN LATERAL (SELECT channels FROM digests
                      WHERE company_id = c.id
                      ORDER BY digest_date DESC LIMIT 1) d ON TRUE
        WHERE c.channel_whatsapp = TRUE AND c.status = 'active'
        """)))

    stats = db.query(
        """
        SELECT (SELECT count(*) FROM companies WHERE status = 'active') AS companies_active,
               (SELECT count(*) FROM opportunities) AS opportunities,
               (SELECT count(*) FROM matches
                  WHERE created_at > now() - %s * INTERVAL '1 hour') AS matches_new,
               (SELECT count(*) FROM digests
                  WHERE created_at > now() - %s * INTERVAL '1 hour') AS digests_sent
        """, (hours, hours))[0]
    stats = {**stats, "requests": dict(req)}
    return checks, stats


def _config_snapshot() -> dict[str, bool]:
    return {
        "kill_switch": bool(config.KILL_SWITCH),
        "portal_enabled": bool(config.PORTAL_ENABLED),
        "llm_enabled": bool(config.LLM_ENABLED),
        "whatsapp_ready": bool(config.WHATSAPP_TOKEN and config.WHATSAPP_PHONE_NUMBER_ID),
        "email_ready": config.email_ready(),
    }


def maybe_alert(report: dict[str, Any]) -> dict[str, Any]:
    """Envoie une alerte si dégradation nouvelle ou cooldown écoulé.

    Anti-spam : on alerte à la première dégradation, quand l'ensemble des
    checks dégradés change, ou après MON_ALERT_COOLDOWN_H sinon.
    Retourne ce qui a été envoyé (jamais d'exception).
    """
    degraded = sorted(c["id"] for c in report.get("checks", [])
                      if c.get("status") != OK)
    result: dict[str, Any] = {"degraded": degraded, "sent": []}

    if not degraded:
        db.set_state(STATE_KEY, {"degraded": [], "ts": time.time(),
                                 "status": report.get("status", OK)})
        result["reason"] = "sain — état réinitialisé"
        return result

    last = db.get_state(STATE_KEY) or {}
    cooldown_s = config.MON_ALERT_COOLDOWN_H * 3600
    due = (not last
           or sorted(last.get("degraded") or []) != degraded
           or time.time() - float(last.get("ts") or 0) > cooldown_s)
    if not due:
        result["reason"] = "dégradation déjà notifiée (cooldown)"
        return result

    db.set_state(STATE_KEY, {"degraded": degraded, "ts": time.time(),
                             "status": report.get("status", WARN)})

    to = config.MON_ALERT_EMAIL or config.ADMIN_USERNAME
    ok_mail, mail_detail = emailer.send_email_html(
        to, f"Soukna — alerte monitoring [{report.get('status', 'warn').upper()}]",
        _alert_html(report, degraded))
    if ok_mail:
        result["sent"].append(f"email:{to}")
    else:
        result["sent"].append(f"email:échec ({mail_detail})")

    if config.MON_ALERT_WHATSAPP:
        ok_wa, wa_detail = whatsapp.send_whatsapp(
            config.MON_ALERT_WHATSAPP, _alert_text(report, degraded))
        result["sent"].append(f"whatsapp:{'envoyé' if ok_wa else wa_detail}")

    return result


def _alert_text(report: dict[str, Any], degraded: list[str]) -> str:
    lines = [f"🚨 Soukna monitoring — statut {report.get('status', '?').upper()}"]
    for c in report.get("checks", []):
        if c.get("status") != OK:
            lines.append(f"• {c['id']} : {c.get('detail', '')}")
    lines.append(f"(fenêtre {report.get('window_hours', '?')}h)")
    return "\n".join(lines + [f"checks: {', '.join(degraded)}"])


def _alert_html(report: dict[str, Any], degraded: list[str]) -> str:
    rows = "".join(
        f"<tr><td style='padding:6px 12px;border-bottom:1px solid #eee;'>"
        f"{c['id']}</td>"
        f"<td style='padding:6px 12px;border-bottom:1px solid #eee;'>"
        f"{c.get('status', '').upper()}</td>"
        f"<td style='padding:6px 12px;border-bottom:1px solid #eee;'>"
        f"{c.get('detail', '')}</td></tr>"
        for c in report.get("checks", []) if c.get("status") != OK)
    return (
        "<div style='font-family:Arial,sans-serif;max-width:640px'>"
        f"<h2 style='color:#b91c1c'>Soukna — alerte monitoring "
        f"[{report.get('status', 'warn').upper()}]</h2>"
        f"<p>Fenêtre analysée : {report.get('window_hours', '?')} heures.</p>"
        "<table style='border-collapse:collapse;font-size:14px'>"
        "<tr style='background:#f7f7f7'><th style='padding:6px 12px;text-align:left'>Check</th>"
        "<th style='padding:6px 12px;text-align:left'>Statut</th>"
        "<th style='padding:6px 12px;text-align:left'>Détail</th></tr>"
        f"{rows}</table>"
        f"<p style='color:#666;font-size:12px'>Checks : {', '.join(degraded)} — "
        "rapport complet : onglet Monitoring de la console d'administration.</p>"
        "</div>")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
