# =====================================================================
# Nœud verdict : GO / À ÉTUDIER / NO-GO + risques (carte verdict-agent).
# LLM en batch + repli par seuils : GO >= 75, NO_GO < 45.
# =====================================================================
from __future__ import annotations

import json
from typing import Any

from .. import config, db
from ..llm import call_llm_json, make_llm
from ..prompts import VERDICT_SYSTEM
from ..state import AgentState
from ..tracing import traced


def _heuristic_verdict(score: int) -> str:
    if score >= config.VERDICT_GO_MIN:
        return "go"
    if score < config.VERDICT_NOGO_MAX:
        return "no_go"
    return "a_etudier"


@traced("verdict", lambda r: f"verdicts={len(r.get('matches') or [])}")
def verdict_node(state: AgentState) -> dict[str, Any]:
    items = list(state.get("matches") or [])
    if not items:
        return {"matches": items}

    llm, _mode = make_llm()
    vmap: dict[str, dict[str, Any]] = {}
    if llm is not None:
        listing = json.dumps([
            {
                "key": f"{it['company_id']}:{it['source_ref']}",
                "match_score": it["match_score"],
                "risks": it["risks"],
                "titre": it["title"],
            }
            for it in items
        ], ensure_ascii=False)
        prompt = (
            VERDICT_SYSTEM
            + "\n\nÉvalue CHAQUE item de la liste (une entrée par key)."
            + '\nRéponds STRICTEMENT en JSON : {"verdicts": '
            + '[{"key": "...", "verdict": "go|a_etudier|no_go", "risks": ["..."]}]}'
            + f"\n\nITEMS : {listing}"
        )
        parsed, _mode = call_llm_json(llm, prompt, {})
        for v in (parsed or {}).get("verdicts") or []:
            if isinstance(v, dict) and v.get("key"):
                vmap[str(v["key"])] = v

    for it in items:
        key = f"{it['company_id']}:{it['source_ref']}"
        v = vmap.get(key)
        if v and v.get("verdict") in {"go", "a_etudier", "no_go"}:
            verdict = v["verdict"]
            risks = [str(r) for r in (v.get("risks") or [])][:4] or it["risks"]
        else:
            verdict = _heuristic_verdict(int(it["match_score"]))
            risks = it["risks"]
        it["verdict"] = verdict
        it["risks"] = risks
        db.set_verdict(it["opportunity_id"], it["company_id"], verdict, risks)

    return {"matches": items}
