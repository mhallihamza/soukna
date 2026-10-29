# =====================================================================
# LLM : extraction JSON tolérante + fabrique (mode heuristique sans clé).
# =====================================================================
from soukna_graph.llm import extract_json, make_llm


def test_extract_json_plain():
    assert extract_json('{"intent": "greeting"}') == {"intent": "greeting"}


def test_extract_json_fenced():
    text = 'Voici le résultat :\n```json\n{"intent": "other", "score": 3}\n```\nmerci'
    assert extract_json(text) == {"intent": "other", "score": 3}


def test_extract_json_nested_braces():
    text = 'texte {"extracted": {"a": 1}, "intent": "opportunities"} fin'
    assert extract_json(text)["intent"] == "opportunities"


def test_extract_json_invalid_returns_none():
    assert extract_json("pas de json ici") is None
    assert extract_json("") is None


def test_make_llm_without_key_is_heuristic(monkeypatch):
    from soukna_graph import config
    monkeypatch.setattr(config, "MISTRAL_API_KEY", "")
    llm, mode = make_llm()
    assert llm is None
    assert mode == "heuristic"
