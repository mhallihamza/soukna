# =====================================================================
# Fabrique LLM : Mistral si disponible, sinon mode heuristique (sans clé).
# MISTRAL_MODEL=codestral-latest est le seul modèle actif sur la clé fournie
# (mistral-small => 429, mistral-large => 403) — ne pas changer sans test.
# =====================================================================
from __future__ import annotations

import json
from typing import Any

import requests

from . import config


def make_llm():
    """Retourne (llm, mode). llm=None en mode heuristique."""
    if config.llm_ready():
        try:
            from langchain_mistralai import ChatMistralAI

            return ChatMistralAI(
                model=config.MISTRAL_MODEL,
                api_key=config.MISTRAL_API_KEY,
                temperature=0.0,
            ), "mistral"
        except Exception:  # dépendance absente ou erreur d'init
            pass
    return None, "heuristic"


def extract_json(text: str) -> dict[str, Any] | None:
    """Prend le premier objet JSON d'un texte (gère les accolades imbriquées)."""
    if not text:
        return None
    text = str(text)
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        depth = 0
        for j in range(i, len(text)):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[i:j + 1]
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict):
                            return obj
                    except (json.JSONDecodeError, ValueError):
                        pass
                    break
    return None


def extract_usage(resp: Any) -> dict[str, int] | None:
    """Tokens consommés par un appel LLM (format langchain ou Mistral)."""
    try:
        um = getattr(resp, "usage_metadata", None)
        if isinstance(um, dict) and um.get("total_tokens"):
            return {"in": int(um.get("input_tokens") or 0),
                    "out": int(um.get("output_tokens") or 0)}
        tu = (getattr(resp, "response_metadata", None) or {}).get("token_usage") or {}
        if tu.get("total_tokens"):
            return {"in": int(tu.get("prompt_tokens") or 0),
                    "out": int(tu.get("completion_tokens") or 0)}
    except Exception:
        pass
    return None


def merge_usage(state: dict[str, Any], usage: dict[str, int] | None) -> dict[str, int] | None:
    """Accumule la consommation LLM dans l'état du graphe (par requête)."""
    if not usage:
        return None
    prev = dict(state.get("llm_usage") or {})
    return {"in": prev.get("in", 0) + usage["in"],
            "out": prev.get("out", 0) + usage["out"]}


def call_llm_json(llm: Any, prompt: str,
                  fallback: dict[str, Any]) -> tuple[dict[str, Any], str, dict[str, int] | None]:
    """Appelle le LLM et exige un objet JSON.
    Repli : `fallback` + mode 'heuristic'. Retourne aussi la consommation."""
    if llm is None:
        return fallback, "heuristic", None
    try:
        resp = llm.invoke(prompt)
        content = getattr(resp, "content", "") or ""
        parsed = extract_json(content)
        if parsed is not None:
            return parsed, "mistral", extract_usage(resp)
    except Exception:  # 429/403/réseau : repli silencieux mais tracé
        pass
    return fallback, "heuristic", None


def mistral_judge(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any] | None:
    """Juge d'évaluation (utilisé par scripts/eval_suite.py). None si clé absente."""
    if not config.llm_ready():
        return None
    prompt = (
        "You are an evaluation judge for the Soukna public-procurement assistant.\n"
        "Compare EXPECTED with ACTUAL and decide if the test passes.\n\n"
        f"EXPECTED:\n{json.dumps(expected, ensure_ascii=False, indent=2)}\n\n"
        f"ACTUAL:\n{json.dumps(actual, ensure_ascii=False, indent=2)}\n\n"
        "Judge semantics, not exact strings. Respond in JSON only:\n"
        '{"verdict": "pass" or "fail", "score": 0-100, "reasoning": "..."}'
    )
    try:
        r = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {config.MISTRAL_API_KEY}"},
            json={
                "model": config.MISTRAL_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "response_format": {"type": "json_object"},
            },
            timeout=60,
        )
        if r.status_code == 200:
            return json.loads(r.json()["choices"][0]["message"]["content"])
    except (requests.RequestException, ValueError, KeyError):
        pass
    return None
