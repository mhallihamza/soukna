# =====================================================================
# Digest : formatage de la synthèse (fr, verdicts, rappel final).
# =====================================================================
import asyncio

from soukna_graph.nodes.digest import REGISTER_HINT, build_digest_text

COMPANY = {"name": "TechMaroc"}
ITEMS = [
    {"title": "Maintenance informatique", "city": "Rabat", "region": "Rabat",
     "deadline": "2026-12-15", "source_ref": "SO-DEM-007", "match_score": 82,
     "verdict": "go", "risks": ["Délai à confirmer"]},
    {"title": "Fourniture de mobilier", "city": "Marrakech", "region": "Marrakech",
     "deadline": "2026-12-20", "source_ref": "SO-DEM-008", "match_score": 55,
     "verdict": "a_etudier", "risks": []},
    {"title": "Réhabilitation bâtiment", "city": "Agadir", "region": "Agadir",
     "deadline": "2026-12-25", "source_ref": "SO-DEM-002", "match_score": 30,
     "verdict": "no_go", "risks": []},
]


def test_digest_contains_header_and_items():
    text = build_digest_text(COMPANY, ITEMS)
    assert "SOUKNA" in text
    assert "TechMaroc" in text
    assert "Maintenance informatique" in text
    assert "Match 82/100" in text
    assert "GO" in text


def test_digest_counts_line():
    text = build_digest_text(COMPANY, ITEMS)
    assert "GO : 1" in text
    assert "étudier : 1" in text
    assert "NO-GO : 1" in text


def test_digest_human_decision_reminder():
    text = build_digest_text(COMPANY, ITEMS)
    assert "décision humaine" in text.lower() or "Décision humaine" in text


def test_digest_empty_items():
    text = build_digest_text(COMPANY, [])
    assert "Aucune nouvelle opportunité" in text


def test_digest_risks_shown():
    text = build_digest_text(COMPANY, ITEMS)
    assert "Délai à confirmer" in text


def test_register_hint_mentions_dashboard():
    assert "dashboard" in REGISTER_HINT.lower()


# --- Mode pipeline : garde anti-fallback seeds ---------------------------

def _run_pipeline_digest(monkeypatch, calls: dict, source_mode: str) -> list[dict]:
    """Exécute digest_node en mode pipeline avec persistance maquée."""
    from soukna_graph.nodes import digest as digest_mod
    items_scoped = [dict(dict(it, company_id="c1")) for it in ITEMS]
    company = {"id": "c1", "name": "TechMaroc", "channel_whatsapp": 1,
               "phone": "+212600000000", "channel_email": 1,
               "email": "a@b.ma"}
    monkeypatch.setattr("soukna_graph.nodes.digest.db.get_company",
                        lambda cid: company)
    monkeypatch.setattr("soukna_graph.nodes.digest.db.save_digest",
                        lambda **kw: calls.setdefault("saves", []).append(kw))
    monkeypatch.setattr("soukna_graph.nodes.digest.send_whatsapp",
                        lambda phone, text: (True, "ok"))
    monkeypatch.setattr("soukna_graph.nodes.digest.send_email",
                        lambda email, subject, text: (True, "ok"))
    asyncio.run(digest_mod.digest_node({"run_pipeline": True, "source_mode": source_mode,
                            "matches": items_scoped}))
    return calls.get("saves", [])


def test_pipeline_seed_fallback_blocks_external_channels(monkeypatch, tmp_path):
    saves = _run_pipeline_digest(monkeypatch, {}, "seed")
    from soukna_graph.nodes.digest import SEED_NOTICE
    assert saves, "aucun digest sauvegardé"
    # Uniquement dashboard, avec le bandeau dans le contenu
    assert all(c.get("channels") == ["dashboard"] for c in saves)
    assert all(SEED_NOTICE in c.get("content", "") for c in saves)


def test_pipeline_real_sources_send_external_channels(monkeypatch, tmp_path):
    calls: dict = {}
    saves = _run_pipeline_digest(monkeypatch, calls, "multi")
    from soukna_graph.nodes.digest import SEED_NOTICE
    assert saves, "aucun digest sauvegardé"
    channels = saves[-1].get("channels", [])
    assert "whatsapp" in channels and "email" in channels
    assert SEED_NOTICE not in saves[-1].get("content", "")
