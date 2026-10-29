# =====================================================================
# Matching (heuristique) + verdict (seuils).
# =====================================================================
from soukna_graph.nodes.matching import _heuristic_match
from soukna_graph.nodes.verdict import _heuristic_verdict

COMPANY = {
    "name": "TechMaroc",
    "sectors": ["Informatique"],
    "keywords": ["informatique", "maintenance"],
    "regions": ["Rabat"],
    "size": "pme",
}

OPP_ALIGNED = {
    "title": "Maintenance informatique multi-sites (parc bureautique)",
    "sector": "Informatique",
    "region": "Rabat",
    "city": "Rabat",
    "deadline": "2099-01-01",
    "amount": "300 000 - 600 000 MAD",
}

OPP_OFF = {
    "title": "Réhabilitation d'un bâtiment administratif",
    "sector": "BTP",
    "region": "Agadir",
    "city": "Agadir",
    "deadline": "2099-01-01",
    "amount": "3 000 000 - 5 000 000 MAD",
}


def test_aligned_scores_high():
    score, reasons, _risks, _bd = _heuristic_match(OPP_ALIGNED, COMPANY)
    assert score >= 75
    assert reasons  # au moins une justification


def test_off_scores_low():
    score, _reasons, _risks, _bd = _heuristic_match(OPP_OFF, COMPANY)
    assert score < 45


def test_score_clamped_0_100():
    score, _r, _k, _bd = _heuristic_match(OPP_ALIGNED, COMPANY)
    assert 0 <= score <= 100


def test_high_amount_flags_risk_for_pme():
    opp = {**OPP_ALIGNED, "amount": "8 000 000 MAD"}
    _score, _reasons, risks, _bd = _heuristic_match(opp, COMPANY)
    assert any("capacité financière" in r for r in risks)


def test_short_deadline_flags_risk():
    from datetime import date, timedelta
    near = (date.today() + timedelta(days=3)).isoformat()
    opp = {**OPP_ALIGNED, "deadline": near}
    _score, _reasons, risks, _bd = _heuristic_match(opp, COMPANY)
    assert any("Délai" in r for r in risks)


def test_verdict_thresholds():
    assert _heuristic_verdict(80) == "go"
    assert _heuristic_verdict(75) == "go"
    assert _heuristic_verdict(60) == "a_etudier"
    assert _heuristic_verdict(45) == "a_etudier"
    assert _heuristic_verdict(30) == "no_go"
    assert _heuristic_verdict(0) == "no_go"


def test_breakdown_factors_0_100():
    _score, _r, _k, bd = _heuristic_match(OPP_ALIGNED, COMPANY)
    assert set(bd) == {"sector", "keywords", "region", "size", "history"}
    assert all(0 <= v <= 100 for v in bd.values())
    assert bd["sector"] >= 80   # secteur aligné
    assert bd["region"] >= 80   # région couverte
