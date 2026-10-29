# =====================================================================
# Seeds : intégrité des fixtures (démarrage pipeline sans portail).
# =====================================================================
from datetime import date

from soukna_graph.tools.seed_data import SEED_OPPORTUNITIES

REQUIRED_KEYS = {"source_ref", "title", "buyer", "city", "region", "sector",
                 "domain_code", "deadline", "amount", "url", "raw"}


def test_eight_seed_opportunities():
    assert len(SEED_OPPORTUNITIES) == 8


def test_source_refs_unique():
    refs = [o["source_ref"] for o in SEED_OPPORTUNITIES]
    assert len(refs) == len(set(refs))
    assert all(ref.startswith("SO-DEM-") for ref in refs)


def test_required_keys_present():
    for opp in SEED_OPPORTUNITIES:
        assert REQUIRED_KEYS.issubset(opp.keys()), opp["source_ref"]


def test_deadlines_are_future_iso_dates():
    for opp in SEED_OPPORTUNITIES:
        dl = date.fromisoformat(opp["deadline"])
        assert dl >= date.today(), opp["source_ref"]


def test_sectors_cover_referential():
    sectors = {o["sector"] for o in SEED_OPPORTUNITIES}
    from soukna_graph import config
    assert sectors.issubset(set(config.SECTORS))
