# =====================================================================
# Digest : formatage de la synthèse (fr, verdicts, rappel final).
# =====================================================================
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
