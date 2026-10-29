# =====================================================================
# Helpers partagés des scripts (compagnie de test, seeds, cleanup).
# =====================================================================
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from soukna_graph import config, db  # noqa: E402
from soukna_graph.graph import build_graph  # noqa: E402
from soukna_graph.tools.seed_data import SEED_OPPORTUNITIES  # noqa: E402

TEST_EMAIL = "eval-test@soukna.ma"
TEST_PHONE = "+212600000001"
TEST_NAME = "Entreprise Test Eval"


async def run_graph(state: dict) -> dict:
    graph = build_graph()
    return await graph.ainvoke(state)


def run_graph_sync(state: dict) -> dict:
    return asyncio.run(run_graph(state))


def ensure_db() -> None:
    db.init_db()


def ensure_test_company() -> dict:
    """Entreprise de test : secteurs/regions/keywords couvrant les seeds."""
    company = db.upsert_company(
        name=TEST_NAME,
        email=TEST_EMAIL,
        phone=TEST_PHONE,
        sectors=["Informatique", "Services et maintenance"],
        keywords=["informatique", "maintenance", "plateforme"],
        regions=["Rabat", "Casablanca"],
        size="pme",
    )
    db.set_channel_prefs(str(company["id"]), True, False)
    return company


def ensure_seeds() -> int:
    count = 0
    for opp in SEED_OPPORTUNITIES:
        try:
            if db.upsert_opportunity(**opp):
                count += 1
        except Exception:
            continue
    return count


def cleanup_test_data() -> dict:
    """Purge toutes les traces de test (préfixe eval- + compagnie de test)."""
    deleted = {}
    deleted["lg_logs"] = db.execute(
        "DELETE FROM lg_logs WHERE request_id IN "
        "(SELECT id FROM lg_requests WHERE message_id LIKE 'eval-%')"
    )
    deleted["lg_requests"] = db.execute(
        "DELETE FROM lg_requests WHERE message_id LIKE 'eval-%'"
    )
    deleted["lg_messages_seen"] = db.execute(
        "DELETE FROM lg_messages_seen WHERE message_id LIKE 'eval-%'"
    )
    deleted["companies"] = db.execute(
        "DELETE FROM companies WHERE email = %s", (TEST_EMAIL,)
    )
    return deleted


def is_kill_switch_safe() -> bool:
    """Le runbook impose KILL_SWITCH=true pour toute exécution de test."""
    return config.KILL_SWITCH
