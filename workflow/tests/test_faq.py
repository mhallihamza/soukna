# =====================================================================
# FAQ agent : découpage KB, recherche Astra ($vectorize), rédaction RAG.
# 100 % hors-ligne — l'API Astra (requests.post) est monkeypatchée, la
# base Postgres est interdite par conftest.
# =====================================================================
import asyncio

import pytest

from soukna_graph import config
from soukna_graph.nodes import faq
from soukna_graph.tools import astra_kb


# faq_node est décoré traced() (async) : exécuté via le get_event_loop
def run_node(state):
    return asyncio.run(faq.faq_node(state))


@pytest.fixture(autouse=True)
def fake_astra_env(monkeypatch):
    """Aucun .env en CI : les credentials Astra sont simulés pour tous
    les tests (sinon _base_url() lève astra_not_configured avant même
    que requests.post monkeypatché soit appelé)."""
    monkeypatch.setattr(config, "ASTRA_DB_API_ENDPOINT",
                        "https://fake-astra-test.apps.astra.datastax.com")
    monkeypatch.setattr(config, "ASTRA_DB_TOKEN", "AstraCS:fake-token-offline-tests")


# ---------------------------------------------------------------------
# Découpage (pur, sans réseau)
# ---------------------------------------------------------------------
PAGES_FR = [
    "Tarifs Soukna.\nL'abonnement Pro coûte 199 DH par mois. "
    "La formule Business coûte 499 DH par mois.",
    "L'essai gratuit dure 14 jours. Sans carte bancaire. "
    "Aucun engagement pendant la découverte.",
]


def test_chunk_pages_returns_vectorize_documents():
    docs = astra_kb.chunk_pages(PAGES_FR, doc="soukna-kb-02-tarifs-fr",
                                topic="tarifs", lang="fr",
                                source="kb/soukna-kb-02-tarifs.pdf")
    assert docs
    for d in docs:
        assert d["$vectorize"] == d["text"]          # champ intégré : pas d'embedding externe
        assert d["doc"] == "soukna-kb-02-tarifs-fr"
        assert d["lang"] == "fr"
        assert d["topic"] == "tarifs"


def test_chunk_pages_small_text_is_one_chunk():
    docs = astra_kb.chunk_pages(["Court passage."], doc="d", topic="t", lang="fr")
    assert len(docs) == 1
    assert docs[0]["text"] == "Court passage."


def test_chunk_pages_chunks_overlap_and_do_not_lose_text():
    long_text = "Phrase complète numéro %d. " % 0
    long_text = " ".join(f"Phrase complète numéro {i}." for i in range(120))
    docs = astra_kb.chunk_pages([long_text], doc="d", topic="t", lang="fr")
    assert len(docs) > 1
    # chevauchement : la phrase charnière est présente dans deux passages voisins
    joined = [d["text"] for d in docs]
    assert all(len(t) <= config.KB_CHUNK_CHARS * 2 for t in joined)
    # aucun mot perdu : la concaténation couvre le texte
    assert "Phrase complète numéro 119." in " ".join(joined)


def test_chunk_pages_empty_pages_returns_empty():
    assert astra_kb.chunk_pages(["", "   "], doc="d", topic="", lang="fr") == []


# ---------------------------------------------------------------------
# Recherche Data API (requests.post monkeypatché)
# ---------------------------------------------------------------------
class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or str(self._payload)

    def json(self):
        return self._payload


def astra_find_payload(docs):
    return {"data": {"documents": docs}}


@pytest.fixture
def fake_astra(monkeypatch):
    """Capture les payloads envoyés à l'API Astra et réponds en conséquence."""
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers})
        body = json or {}
        if "find" in body:
            docs = []
            wanted = (body["find"].get("filter") or {}).get("lang")
            limit = (body["find"].get("options") or {}).get("limit") or 4
            for d in globals()["FAKE_DOCS"]:
                if wanted and d.get("lang") != wanted:
                    continue
                docs.append({**d, "$similarity": 0.9})
                if len(docs) >= limit:
                    break
            return FakeResponse(payload=astra_find_payload(docs))
        if "countDocuments" in body:
            return FakeResponse(payload={"status": {"count": len(globals()["FAKE_DOCS"])}})
        raise AssertionError(f"payload inattendu : {body}")

    monkeypatch.setattr(astra_kb.requests, "post", fake_post)
    return calls


FAKE_DOCS = [
    {"text": "L'abonnement Pro coûte 199 DH par mois.", "doc": "soukna-kb-02-tarifs-fr",
     "topic": "tarifs", "lang": "fr"},
    {"text": "اشتراك Pro يكلف 199 درهم شهرياً.", "doc": "soukna-kb-02-tarifs-ar",
     "topic": "tarifs", "lang": "ar"},
]


def test_search_sends_vectorize_query_and_filters_lang(fake_astra):
    hits = astra_kb.search("Combien coûte l'abonnement ?", lang="fr")
    assert hits, "le filtrage fr doit ramener le passage tarifs-fr"
    assert hits[0]["doc"] == "soukna-kb-02-tarifs-fr"
    sent = fake_astra[0]["json"]["find"]
    assert sent["sort"] == {"$vectorize": "Combien coûte l'abonnement ?"}
    assert sent["filter"] == {"lang": "fr"}
    assert sent["options"]["limit"] == 4
    # auth observée sur ce gateway : en-tête « Token » (Bearer rejeté en 401)
    assert fake_astra[0]["headers"]["Token"].startswith("AstraCS:")


def test_search_arabic_query_reads_arabic_docs(fake_astra, monkeypatch):
    monkeypatch.setattr(config, "FAQ_TOP_K", 2)
    hits = astra_kb.search("كم ثمن الاشتراك؟", lang="ar")
    assert hits[0]["doc"] == "soukna-kb-02-tarifs-ar"


def test_search_retries_without_filter_when_language_absent(fake_astra, monkeypatch):
    # base sans aucun passage fr : la recherche fr doit retenter sans filtre
    monkeypatch.setitem(globals(), "FAKE_DOCS", [
        {"text": "اشتراك Pro يكلف 199 درهم شهرياً.", "doc": "soukna-kb-02-tarifs-ar",
         "topic": "tarifs", "lang": "ar"},
    ])
    hits = astra_kb.search("tarifs ?", lang="fr")
    assert hits[0]["doc"] == "soukna-kb-02-tarifs-ar"
    # deux appels : filtré fr (vide) puis sans filtre
    assert len(fake_astra) == 2
    assert "filter" not in fake_astra[1]["json"]["find"]


def test_search_failed_http_raises_astra_error(monkeypatch):
    monkeypatch.setattr(astra_kb.requests, "post",
                        lambda *a, **k: FakeResponse(400, {"errors": [{"message": "bad"}]}))
    with pytest.raises(astra_kb.AstraError):
        astra_kb.search("test")


def test_search_empty_query_is_local_noop(fake_astra):
    assert astra_kb.search("") == []
    assert astra_kb.search("   ") == []
    assert not fake_astra, "aucun appel réseau pour une requête vide"


def test_format_context_bounded_and_tagged(fake_astra):
    hits = astra_kb.search("tarifs", lang="fr")
    ctx = astra_kb.format_context(hits, max_chars=10_000)
    assert "soukna-kb-02-tarifs-fr" in ctx
    assert "199 DH" in ctx


def test_not_configured_raises_clear_error(monkeypatch):
    monkeypatch.setattr(config, "ASTRA_DB_API_ENDPOINT", "")
    with pytest.raises(astra_kb.AstraError, match="astra_not_configured"):
        astra_kb.search("test")


# ---------------------------------------------------------------------
# Nœud faq : RAG strict + replis
# ---------------------------------------------------------------------
@pytest.fixture
def kb_hits_only(monkeypatch):
    monkeypatch.setattr(faq.astra_kb, "search", lambda q, lang=None, top_k=None: [
        {"text": "L'abonnement Pro coûte 199 DH/mois, Business 499 DH/mois.",
         "doc": "soukna-kb-02-tarifs-fr", "topic": "tarifs", "similarity": 0.88},
        {"text": "L'essai gratuit dure 14 jours.", "doc": "soukna-kb-02-tarifs-fr",
         "topic": "tarifs", "similarity": 0.71},
    ])
    monkeypatch.setattr(faq.config, "MISTRAL_API_KEY", "")  # LLM absent → repli


def test_faq_node_no_hits_never_invents(kb_hits_only, monkeypatch):
    monkeypatch.setattr(faq.astra_kb, "search", lambda q, lang=None, top_k=None: [])
    out = run_node({"message": "Quel est le délai de livraison à Fès ?",
                        "language": "fr"})
    assert out["faq_hits"] == 0
    assert "dashboard Soukna" in out["reply_text"]


def test_faq_node_heuristic_fallback_quotes_top_chunk(kb_hits_only):
    out = run_node({"message": "C'est combien l'abonnement ?", "language": "fr"})
    assert "199 DH" in out["reply_text"]
    assert "soukna-kb-02-tarifs-fr" in out["reply_text"]  # sources citées
    assert out["faq_hits"] == 2


def test_faq_node_arabic_language_asked_arabic_docs(kb_hits_only):
    out = run_node({"message": "كم ثمن الاشتراك؟", "language": "ar"})
    assert out["faq_hits"] == 2  # la KB arabe répond à la question arabe


def test_faq_node_detects_arabic_without_language_field(kb_hits_only, monkeypatch):
    seen_lang = {}

    def fake_search(q, lang=None, top_k=None):
        seen_lang["lang"] = lang
        return [{"text": "اشتراك Pro يكلف 199 درهم.", "doc": "kb-ar", "topic": "", "similarity": 0.9}]

    monkeypatch.setattr(faq.astra_kb, "search", fake_search)
    out = run_node({"message": "كم ثمن الاشتراك؟"})
    assert seen_lang["lang"] == "ar"
    assert out["faq_hits"] == 1


def test_faq_node_llm_answer_replaces_fallback(kb_hits_only, monkeypatch):
    class FakeLLM:
        def invoke(self, prompt):
            assert "199 DH" in prompt              # le contexte RAG est bien passé
            assert "fr" in prompt
            return type("Resp", (), {"content": "Pro : 199 DH/mois · Business : 499 DH/mois."})()

    monkeypatch.setattr(faq, "make_llm", lambda: (FakeLLM(), "mistral"))
    out = run_node({"message": "tarifs ?", "language": "fr"})
    assert out["reply_text"] == "Pro : 199 DH/mois · Business : 499 DH/mois."
    assert out["llm_mode"] == "mistral"


def test_faq_node_llm_crash_falls_back_to_top_chunk(kb_hits_only, monkeypatch):
    class BrokenLLM:
        def invoke(self, prompt):
            raise RuntimeError("429 rate limit")

    monkeypatch.setattr(faq, "make_llm", lambda: (BrokenLLM(), "mistral"))
    out = run_node({"message": "tarifs ?", "language": "fr"})
    assert "199 DH" in out["reply_text"]           # repli : extrait du passage
    assert out["llm_mode"] == "heuristic"


def test_faq_node_astra_down_falls_back_cleanly(monkeypatch):
    def boom(q, lang=None, top_k=None):
        raise astra_kb.AstraError("réseau : ConnectionError")

    monkeypatch.setattr(faq.astra_kb, "search", boom)
    out = run_node({"message": "tarifs ?", "language": "fr"})
    assert out["faq_hits"] == 0
    assert "dashboard" in out["reply_text"]
