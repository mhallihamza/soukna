# =====================================================================
# Nœud matching : score Match /100 par (entreprise × opportunité).
# LLM en batch (1 appel par entreprise) + repli heuristique déterministe.
# =====================================================================
from __future__ import annotations

import json
import re
from datetime import date as _date
from typing import Any

from .. import db
from ..llm import call_llm_json, make_llm, merge_usage
from ..prompts import MATCHING_SYSTEM
from ..state import AgentState
from ..tracing import traced


def _breakdown(opp: dict[str, Any], company: dict[str, Any]) -> dict[str, int]:
    """Facteurs 0-100 affichés dans le drawer du dashboard."""
    osec = (opp.get("sector") or "").strip().lower()
    csecs = [s.strip().lower() for s in (company.get("sectors") or [])]
    if osec and osec in csecs:
        sector = 90
    elif not osec:
        sector = 55
    else:
        sector = 30

    oreg = (opp.get("region") or opp.get("city") or "").strip().lower()
    cregs = [r.strip().lower() for r in (company.get("regions") or [])]
    if oreg and oreg in cregs:
        region = 95
    elif not oreg:
        region = 55
    else:
        region = 30

    title = (opp.get("title") or "").lower()
    hits = [k for k in (company.get("keywords") or []) if k and k.strip().lower() in title]
    keywords = min(100, 35 + 25 * len(hits))

    digits = re.findall(r"\d{4,}", (opp.get("amount") or "").replace(" ", ""))
    if not digits:
        size = 65
    else:
        ceiling = max(int(n) for n in digits)
        if ceiling < 1_000_000:
            size = 85
        elif ceiling < 5_000_000:
            size = 70
        else:
            size = 75 if (company.get("size") or "pme") == "grande" else 40

    return {"sector": sector, "keywords": keywords, "region": region,
            "size": size, "history": 50}


def _heuristic_match(opp: dict[str, Any],
                     company: dict[str, Any]) -> tuple[int, list[str], list[str], dict[str, int]]:
    """Scoring sans LLM : secteur (50) + géographie (25) + mots-clés (15)."""
    score = 0
    reasons: list[str] = []
    risks: list[str] = []

    osec = (opp.get("sector") or "").strip().lower()
    csecs = [s.strip().lower() for s in (company.get("sectors") or [])]
    if osec and osec in csecs:
        score += 50
        reasons.append(f"Secteur aligné ({opp.get('sector')}).")
    elif osec:
        score += 10
    else:
        score += 25
        reasons.append("Secteur non précisé sur l'annonce.")

    oreg = (opp.get("region") or opp.get("city") or "").strip().lower()
    cregs = [r.strip().lower() for r in (company.get("regions") or [])]
    if oreg and oreg in cregs:
        score += 25
        reasons.append(f"Zone géographique couverte ({opp.get('region') or opp.get('city')}).")
    elif oreg:
        score += 5
    else:
        score += 12

    title = (opp.get("title") or "").lower()
    hits = [k for k in (company.get("keywords") or []) if k and k.strip().lower() in title]
    if hits:
        score += min(15, 5 * len(hits))
        reasons.append("Mots-clés présents : " + ", ".join(hits[:3]) + ".")

    amount_digits = re.findall(r"\d{4,}", (opp.get("amount") or "").replace(" ", ""))
    if amount_digits:
        ceiling = max(int(n) for n in amount_digits)
        if ceiling >= 5_000_000 and (company.get("size") or "pme") in {"petite", "pme"}:
            risks.append("Montant élevé : vérifier la capacité financière exigée.")
            score -= 10

    deadline = str(opp.get("deadline") or "")
    if deadline:
        try:
            days = (_date.fromisoformat(deadline[:10]) - _date.today()).days
            if 0 <= days <= 5:
                risks.append("Délai de réponse court : à confirmer.")
        except ValueError:
            pass

    if "visite" in title:
        risks.append("Visite obligatoire possible : vérifier l'avis.")
    if "garantie" in title or "caution" in title:
        risks.append("Garantie provisoire à préparer.")

    return max(0, min(100, score)), reasons, risks, _breakdown(opp, company)


def _score_batch(llm: Any, company: dict[str, Any],
                 opps: list[dict[str, Any]]) -> tuple[list[tuple[int, list[str], list[str], dict[str, int]]], dict[str, int] | None]:
    """1 appel LLM pour toutes les opportunités d'une entreprise ; repli total."""
    results = [_heuristic_match(o, company) for o in opps]
    usage = None
    if llm is None:
        return results, None

    profile = json.dumps({
        "secteurs": company.get("sectors"),
        "mots_cles": company.get("keywords"),
        "regions": company.get("regions"),
        "taille": company.get("size"),
        # Profil étendu (optionnel — précision du score : budget vs montant,
        # certifications exigées, qualification/classement, types préférés)
        "budget_min": str(company.get("budget_min") or "") or None,
        "budget_max": str(company.get("budget_max") or "") or None,
        "certifications": company.get("certifications") or [],
        "qualification": company.get("qualification") or "",
        "experience_annees": company.get("experience_years"),
        "types_preferes": company.get("prefers_types") or [],
    }, ensure_ascii=False)
    opps_json = json.dumps([{
        "source_ref": o.get("source_ref"),
        "titre": o.get("title"),
        "secteur": o.get("sector"),
        "ville": o.get("city"),
        "region": o.get("region"),
        "echeance": str(o.get("deadline") or ""),
        "montant": o.get("amount"),
    } for o in opps], ensure_ascii=False)
    prompt = (
        MATCHING_SYSTEM
        + "\n\nÉvalue CHAQUE opportunité de la liste contre le PROFIL "
        + "(une entrée par opportunité, même ordre et mêmes source_ref)."
        + '\nRéponds STRICTEMENT en JSON : {"matches": [{"source_ref": "...", '
        + '"match_score": 0-100, "reasons": ["..."], "risks": ["..."]}]}'
        + f"\n\nPROFIL : {profile}\n\nOPPORTUNITÉS : {opps_json}"
    )
    parsed, _mode, usage = call_llm_json(llm, prompt, {})
    by_ref: dict[str, dict[str, Any]] = {}
    for m in (parsed or {}).get("matches") or []:
        if isinstance(m, dict) and m.get("source_ref"):
            by_ref[str(m["source_ref"])] = m

    for i, opp in enumerate(opps):
        m = by_ref.get(str(opp.get("source_ref")))
        if not m:
            continue  # l'heuristique reste en place pour cette ligne
        try:
            score = max(0, min(100, int(m.get("match_score", results[i][0]))))
        except (TypeError, ValueError):
            score = results[i][0]
        reasons = [str(r) for r in (m.get("reasons") or [])][:3] or results[i][1]
        risks = [str(r) for r in (m.get("risks") or [])][:4]
        results[i] = (score, reasons, risks, results[i][3])
    return results, usage


@traced("matching", lambda r: f"matches={len(r.get('matches') or [])}")
def matching_node(state: AgentState) -> dict[str, Any]:
    pipeline = bool(state.get("run_pipeline"))
    if pipeline:
        companies = db.list_companies()
    else:
        company = state.get("company")
        companies = [company] if company else []

    llm, _mode = make_llm()
    items: list[dict[str, Any]] = []
    usage_state = None
    for company in companies:
        if not company:
            continue
        opps = db.opportunities_without_match(str(company["id"]), limit=10)
        if not opps:
            continue
        batch, usage = _score_batch(llm, company, opps)
        for opp, (score, reasons, risks, breakdown) in zip(opps, batch):
            db.upsert_match(
                opportunity_id=str(opp["id"]),
                company_id=str(company["id"]),
                match_score=score,
                reasons=reasons,
                verdict="",
                risks=risks,
                breakdown=breakdown,
            )
            items.append({
                "company_id": str(company["id"]),
                "company_name": company.get("name", ""),
                "company_phone": company.get("phone") or "",
                "company_email": company.get("email") or "",
                "channel_whatsapp": bool(company.get("channel_whatsapp")),
                "channel_email": bool(company.get("channel_email")),
                "opportunity_id": str(opp["id"]),
                "source_ref": opp.get("source_ref"),
                "title": opp.get("title"),
                "city": opp.get("city"),
                "region": opp.get("region"),
                "deadline": str(opp.get("deadline") or ""),
                "amount": opp.get("amount") or "",
                "match_score": score,
                "reasons": reasons,
                "risks": risks,
                "verdict": "",
            })
        usage_state = merge_usage(state, usage) or usage_state
    return {"matches": items, "llm_usage": usage_state}
