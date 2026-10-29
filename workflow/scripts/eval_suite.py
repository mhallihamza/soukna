# =====================================================================
# eval_suite.py — 10 cas sur le VRAI graphe + juge LLM (ou heuristique).
# Nettoyage AVANT et APRÈS (try/finally) ; --no-clean garde les données
# pour une démo dashboard.
# =====================================================================
from __future__ import annotations

import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    TEST_PHONE,
    cleanup_test_data,
    ensure_db,
    ensure_seeds,
    ensure_test_company,
    run_graph,
)

from soukna_graph.llm import mistral_judge  # noqa: E402

CASES_PATH = ROOT / "tests" / "test_cases.json"
ARTIFACTS = ROOT / "artifacts"


def heuristic_judge(expected: dict, actual: dict) -> dict:
    """Juge sans clé LLM : intent exact + mots-clés présents dans la réponse."""
    reply = (actual.get("reply") or "").lower()
    intent_ok = actual.get("intent") == expected.get("intent")
    keywords = [k.lower() for k in expected.get("reply_contains", [])]
    keywords_ok = all(k in reply for k in keywords)
    checks = [intent_ok, keywords_ok] if keywords else [intent_ok]
    score = int(100 * sum(1 for c in checks if c) / len(checks))
    return {
        "verdict": "pass" if all(checks) else "fail",
        "score": score,
        "reasoning": "heuristic: intent=" + str(intent_ok) + " keywords=" + str(keywords_ok),
    }


async def run_case(case: dict) -> dict:
    result = await run_graph({
        "message": case["message"],
        "sender_phone": TEST_PHONE,
        "sender_name": "Eval Soukna",
        "message_id": f"eval-{case['id']}-{uuid.uuid4()}",
    })
    return {
        "intent": result.get("intent"),
        "reply": result.get("reply_text") or "",
        "route": result.get("route"),
    }


async def main() -> int:
    no_clean = "--no-clean" in sys.argv
    ensure_db()
    if not no_clean:
        cleanup_test_data()
    ensure_test_company()
    ensure_seeds()

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    results = []
    for case in cases:
        try:
            actual = await run_case(case)
        except Exception as exc:
            actual = {"intent": None, "reply": "", "error": f"{type(exc).__name__}: {exc}"}
        expected = case["expected"]
        judge = mistral_judge(expected, actual) or heuristic_judge(expected, actual)
        results.append({
            "id": case["id"],
            "message": case["message"],
            "expected_intent": expected.get("intent"),
            "actual_intent": actual.get("intent"),
            "verdict": judge.get("verdict"),
            "score": judge.get("score"),
            "reasoning": judge.get("reasoning"),
            "reply_excerpt": (actual.get("reply") or "")[:180],
        })
        status = "✅" if judge.get("verdict") == "pass" else "❌"
        print(f"{status} {case['id']:28} intent={actual.get('intent')} "
              f"score={judge.get('score')}")

    passed = sum(1 for r in results if r["verdict"] == "pass")
    total = len(results)
    print("-" * 60)
    print(f"RÉSULTAT : {passed}/{total} cas réussis")

    ARTIFACTS.mkdir(exist_ok=True)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "total": total,
        "results": results,
    }
    report_path = ARTIFACTS / "eval_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"rapport : {report_path}")

    try:
        if not no_clean:
            cleanup_test_data()
            print("cleanup : données de test purgées")
    finally:
        return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
