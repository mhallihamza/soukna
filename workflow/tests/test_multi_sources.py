# =====================================================================
# Multi-sources : adaptateur RSS générique, normalisation (types AO/BC),
# nœud sources multi-sources résilient, mémoire de conversation, filtres
# de matching. 100 % hors-ligne (db et réseau monkeypatchés).
# =====================================================================
import asyncio

import pytest

from soukna_graph import db, monitoring  # noqa: F401  (db monkeypatché par conftest)
from soukna_graph.nodes import sources as sources_mod
from soukna_graph.nodes.sources import sources_node
from soukna_graph.tools.scrapers import base as sc_base
from soukna_graph.tools.scrapers import generic_rss

RSS_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Portail Régional</title>
  <item>
    <title> Bon de commande n°45 — acquisition de mobilier de bureau </title>
    <link>https://exemple.ma/ao/45</link>
    <guid>bc-45</guid>
    <pubDate>Fri, 30 Oct 2026 09:00:00 GMT</pubDate>
    <description>&lt;p&gt;Fourniture de mobilier pour la province&lt;/p&gt;</description>
  </item>
  <item>
    <title>Appel d'offres ouvert n°12 — étude de faisabilité numérique</title>
    <link>https://exemple.ma/ao/12</link>
    <guid>ao-12</guid>
    <pubDate>Wed, 28 Oct 2026 09:00:00 GMT</pubDate>
  </item>
</channel></rss>"""


# --- Normalisation & types ------------------------------------------------

def test_infer_type_bon_de_commande():
    assert sc_base.infer_opportunity_type("Bon de commande 45/2026") == "bon_commande"
    assert sc_base.infer_opportunity_type("Réparation X", "BC-45") == "bon_commande"


def test_infer_type_default_appel_offres():
    assert sc_base.infer_opportunity_type("Appel d'offres ouvert n°12") == "appel_offres"
    assert sc_base.infer_opportunity_type("Travaux de câblage", "ref99") == "appel_offres"


def test_normalize_item_adds_ref_and_type():
    out = sc_base.normalize_item({"title": "Bon de commande mobilier"}, "Portail Régional")
    assert out["source_ref"].startswith("portail-regional:")
    assert out["opportunity_type"] == "bon_commande"
    assert out["source"] == "portail-regional"


# --- RSS générique ----------------------------------------------------------

def test_generic_rss_parses_fixture(monkeypatch):
    class _R:
        text = RSS_FIXTURE
        def raise_for_status(self): pass
    monkeypatch.setattr(generic_rss.requests, "get", lambda *a, **k: _R())
    items = generic_rss.fetch({"name": "Portail Régional", "base_url": "https://exemple.ma/rss"})
    assert len(items) == 2
    by_ref = {i["source_ref"].split(":", 1)[-1]: i for i in items}
    assert by_ref["bc-45"]["opportunity_type"] == "bon_commande"
    assert by_ref["ao-12"]["opportunity_type"] == "appel_offres"
    assert by_ref["ao-12"]["url"] == "https://exemple.ma/ao/12"


def test_generic_rss_empty_feed_raises(monkeypatch):
    class _R:
        text = "<?xml version=\"1.0\"?><rss version=\"2.0\"><channel/></rss>"
        def raise_for_status(self): pass
    monkeypatch.setattr(generic_rss.requests, "get", lambda *a, **k: _R())
    with pytest.raises(RuntimeError):
        generic_rss.fetch({"name": "X", "base_url": "https://x/rss"})


# --- Nœud sources multi-sources --------------------------------------------

def _patch_db_sources(monkeypatch, rows, statuses):
    monkeypatch.setattr(sources_mod.db, "sources_list", lambda **k: rows)
    monkeypatch.setattr(sources_mod.db, "sources_update_status",
                        lambda sid, st: statuses.append((sid, st)))
    saved = []
    monkeypatch.setattr(sources_mod.db, "upsert_opportunity",
                        lambda **o: saved.append(o["source_ref"]) or True)
    return saved


def test_sources_node_multi_source_resilient(monkeypatch):
    statuses: list = []
    rows = [
        {"id": "s1", "name": "Portail national", "base_url": "u1", "kind": "portal_html",
         "adapter": "marchespublics", "enabled": True, "cadence_hours": 24},
        {"id": "s2", "name": "Régional RSS", "base_url": "u2", "kind": "rss",
         "adapter": "generic_rss", "enabled": True, "cadence_hours": 12},
        {"id": "s3", "name": "Cassée", "base_url": "u3", "kind": "rss",
         "adapter": "generic_rss", "enabled": True, "cadence_hours": 12},
    ]
    saved = _patch_db_sources(monkeypatch, rows, statuses)
    monkeypatch.setattr(sources_mod, "get_adapter", lambda name: {
        "marchespublics": lambda s: [{"source_ref": "portal:a1", "title": "AO A",
                                      "opportunity_type": "appel_offres"}],
        "generic_rss": lambda s: ([{"source_ref": "rss:b1", "title": "BC B",
                                    "opportunity_type": "bon_commande"}]
                                  if s["id"] == "s2"
                                  else (_ for _ in ()).throw(RuntimeError("boom"))),
    }[name])
    result = asyncio.run(sources_node({"run_pipeline": True}))
    assert result["source_mode"] == "multi"
    assert result["ingested"] == 2
    assert len(saved) == 2
    stats = dict(statuses)
    assert stats["s1"].startswith("ok") and stats["s2"].startswith("ok")
    assert stats["s3"].startswith("failed")


def test_sources_node_registry_empty_uses_legacy_portal(monkeypatch):
    statuses: list = []
    saved = _patch_db_sources(monkeypatch, [], statuses)
    monkeypatch.setattr(sources_mod.config, "PORTAL_ENABLED", True)
    monkeypatch.setattr(sources_mod, "get_adapter",
                        lambda name: (lambda s: [{"source_ref": "portal:x", "title": "AO X"}]))
    result = asyncio.run(sources_node({"run_pipeline": True}))
    assert result["ingested"] == 1 and "portal(legacy)" in result["source_detail"]
    assert saved == ["portal:x"]


def test_sources_node_all_fail_falls_back_to_seeds(monkeypatch):
    statuses: list = []
    _patch_db_sources(monkeypatch, [
        {"id": "s1", "name": "Cassée", "base_url": "u", "kind": "rss",
         "adapter": "generic_rss", "enabled": True, "cadence_hours": 12},
    ], statuses)
    monkeypatch.setattr(sources_mod, "get_adapter",
                        lambda name: (lambda s: (_ for _ in ()).throw(RuntimeError("down"))))
    monkeypatch.setattr(sources_mod.seed_data, "SEED_OPPORTUNITIES",
                        [{"source_ref": "seed:1", "title": "Seed"}])
    result = asyncio.run(sources_node({"run_pipeline": True}))
    assert result["source_mode"] == "seed" and result["ingested"] == 1


def test_sources_node_skips_chat_mode():
    assert asyncio.run(sources_node({})) == {"ingested": 0, "source_mode": "skip"}


# --- Mémoire de conversation -----------------------------------------------

def test_chat_roundtrip(monkeypatch):
    store: list[tuple] = []
    monkeypatch.setattr(db, "execute",
                        lambda sql, params=(): store.append(tuple(params)) and None or 1)
    rows = [{"role": "user", "content": "Bonjour", "created_at": "t1"},
            {"role": "assistant", "content": "Bonjour !", "created_at": "t2"}]
    monkeypatch.setattr(db, "query",
                        lambda sql, params=(): list(reversed(rows[-params[1]:])))
    db.chat_save("2126", "user", "Bonjour")
    assert store[0][0] == "2126" and store[0][1] == "user"
    hist = db.chat_history("2126", limit=8)
    assert [h["role"] for h in hist] == ["user", "assistant"]  # ancien → récent


def test_chat_history_empty(monkeypatch):
    monkeypatch.setattr(db, "query", lambda sql, params=(): [])
    assert db.chat_history("inconnu") == []


# --- Filtres de matching ----------------------------------------------------

def test_matches_for_company_builds_filters(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(db, "query", lambda sql, params=(): (captured.update(
        {"sql": sql, "params": params}) or [{"id": "m1"}]))
    rows = db.matches_for_company("c1", min_score=70, opp_type="bon_commande",
                                  sector="informatique", city="Casa")
    assert rows and rows[0]["id"] == "m1"
    assert "opportunity_type = %s" in captured["sql"]
    assert captured["params"][0] == "c1" and captured["params"][1] == 70
    assert "bon_commande" in captured["params"]


def test_matches_for_company_no_filters(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(db, "query", lambda sql, params=(): (captured.update(
        {"sql": sql, "params": params}) or []))
    db.matches_for_company("c1")
    assert "opportunity_type = %s" not in captured["sql"]


def test_sources_upsert_accepts_enabled_kwarg(monkeypatch):
    """Régression : le POST admin envoie `enabled` — sources_upsert doit
    l'accepter (TypeError silencieux => 500 sur le POST, cf. prod)."""
    captured: dict = {}
    monkeypatch.setattr(db, "query", lambda sql, params=(): (captured.update(
        {"sql": sql, "params": params}) or [{"id": "s9"}]))
    row = db.sources_upsert(name="X", base_url="https://x/rss", kind="rss",
                            adapter="generic_rss", cadence_hours=12, enabled=True)
    assert row["id"] == "s9"
    assert "enabled" in captured["sql"] and "COALESCE" in captured["sql"]
    # update : enabled partiel passe aussi
    row = db.sources_upsert(name="X2", base_url="https://x2", source_id="s9",
                            enabled=False)
    assert captured["params"][-1] == "s9"
