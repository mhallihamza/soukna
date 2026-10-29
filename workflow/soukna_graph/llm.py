# =====================================================================
# Fabrique LLM : Mistral si disponible, sinon mode heuristique (sans clé).
# MISTRAL_MODEL=codestral-latest est le seul modèle actif sur la clé fournie
# (mistral-small => 429, mistral-large => 403) — ne pas changer sans test.
# =====================================================================
from __future__ import annotations

import json
import re
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
    """Prend le premier objet JSON d'un texte (tolère les fences)."""
    if not text:
        return None
    candidates = re.findall(r"\{.*?\}", str(text), flags=re.DOTALL)
    for cand in candidates:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, ValueError):
            continue
    return None


def call_llm_json(llm: Any, prompt: str, fallback: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Appelle le LLM et exige un objet JSON. Repli : `fallback` + mode 'heuristic'."""
    if llm is None:
        return fallback, "heuristic"
    try:
        resp = llm.invoke(prompt)
        content = getattr(resp, "content", "") or ""
        parsed = extract_json(content)
        if parsed is not None:
            return parsed, "mistral"
    except Exception:  # 429/403/réseau : repli silencieux mais tracé
        pass
    return fallback, "heuristic"


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
