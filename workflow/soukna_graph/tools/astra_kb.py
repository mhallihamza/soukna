# =====================================================================
# tools/astra_kb.py — base de connaissances FAQ sur DataStax Astra.
#
# Data API v2 (HTTPS + JSON) — le même style que tools/whatsapp.py.
# Embedding INTÉGRÉ à Astra (service NVIDIA) : les documents portent un
# champ "$vectorize" et les requêtes aussi — aucun appel externe
# d'embedding, aucune clé supplémentaire.
#
# Modèle des documents :
#   { "text": ..., "$vectorize": ..., "doc": "soukna-kb-02-tarifs-fr",
#     "topic": "tarifs", "lang": "fr", "source": "kb/soukna-kb-02-tarifs.pdf" }
# =====================================================================
from __future__ import annotations

import requests

from .. import config

HTTP_TIMEOUT = 60
INSERT_BATCH = 20  # insertMany par lots : payloads bornés

# Gateway observé : ce déploiement exige un en-tête d'authentification
# « Token » (formuls « Authorization: Bearer »/« X-Cassandra-Token » non
# acceptés par ce DBCustomEndpoint). Trois variantes essayées par ordre.
_AUTH_VARIANTS = ("Token", "X-Cassandra-Token", "Authorization")

VECTOR_SERVICE = {  # embedding intégré Astra (service NVIDIA de ce DB)
    "provider": "nvidia",
    "modelName": "nvidia/nv-embedqa-e5-v5",
}


class AstraError(Exception):
    pass


def _base_url() -> str:
    endpoint = (config.ASTRA_DB_API_ENDPOINT or "").rstrip("/")
    if not endpoint or not config.ASTRA_DB_TOKEN:
        raise AstraError("astra_not_configured")
    return f"{endpoint}/api/json/v1/{config.ASTRA_DB_KEYSPACE}"


def _headers(variant: str) -> dict:
    if variant == "Token":
        return {"Token": config.ASTRA_DB_TOKEN,
                "Content-Type": "application/json", "Accept": "application/json"}
    if variant == "X-Cassandra-Token":
        return {"X-Cassandra-Token": config.ASTRA_DB_TOKEN,
                "Content-Type": "application/json", "Accept": "application/json"}
    return {"Authorization": f"Bearer {config.ASTRA_DB_TOKEN}",
            "Content-Type": "application/json", "Accept": "application/json"}


def _post(url: str, payload: dict) -> dict:
    """POST Data API ; l'authentification retente sur chaque variante d'en-tête."""
    last_status, last_detail = 0, ""
    for i, variant in enumerate(_AUTH_VARIANTS):
        try:
            r = requests.post(url, headers=_headers(variant), json=payload,
                              timeout=HTTP_TIMEOUT)
        except requests.RequestException as exc:
            raise AstraError(f"réseau : {type(exc).__name__}") from exc
        if r.status_code in (200, 201):
            return r.json()
        last_status = r.status_code
        try:
            errs = r.json().get("errors") or []
            last_detail = "; ".join(e.get("message", "") for e in errs)[:200]
        except ValueError:
            last_detail = (r.text or "")[:120]
        if not (last_status == 401 and i + 1 < len(_AUTH_VARIANTS)
                and "MISSING_AUTHENTICATION" in last_detail.upper()):
            break  # un vrai 401 (toutes variantes échouent) ou une autre erreur
    raise AstraError(f"HTTP {last_status} : {last_detail or 'erreur Astra'}")


# ---------------------------------------------------------------------
# Collection (identifiée par findCollections ; créée si absente)
# ---------------------------------------------------------------------
def _collection_exists() -> bool | None:
    try:
        # {} (pas de nameOnly : cette option n'est pas supportée partout) ;
        # les noms reviennent en chaînes ou en {"name": ...}, les deux gérés.
        data = _post(_base_url(), {"findCollections": {}})
    except AstraError:
        return None  # API injoignable : on ne sait pas
    names = (data.get("status") or {}).get("collections") or []
    names = [c if isinstance(c, str) else (c or {}).get("name", "") for c in names]
    return config.ASTRA_DB_COLLECTION in names


def ensure_collection() -> bool:
    """Crée la collection (embedding NVIDIA intégré) si absente.
    True si elle était déjà prête, False si créée à l'instant."""
    name = config.ASTRA_DB_COLLECTION
    if _collection_exists():
        return True
    _post(_base_url(), {"createCollection": {
        "name": name,
        "options": {"vector": {"service": VECTOR_SERVICE}},
    }})
    return False


def count_documents() -> int:
    """Nombre de passages dans la collection (validé live : status.count)."""
    data = _post(f"{_base_url()}/{config.ASTRA_DB_COLLECTION}",
                 {"countDocuments": {}})
    return int(((data.get("status") or {}).get("count")) or 0)


def delete_source(docs: list[str]) -> int:
    """Supprime les passages d'une source (ré-ingestion sans doublons)."""
    data = _post(f"{_base_url()}/{config.ASTRA_DB_COLLECTION}",
                 {"deleteMany": {"filter": {"doc": {"$in": docs}}}})
    return int(((data.get("status") or {}).get("deletedCount")) or 0)


# ---------------------------------------------------------------------
# Découpage PDF → documents ($vectorize par passage)
# ---------------------------------------------------------------------
def chunk_pages(pages: list[str], *, doc: str, topic: str = "", lang: str = "",
                source: str = "", target_chars: int | None = None,
                overlap: int = 150) -> list[dict]:
    """Fusionne des pages en passages ~target_chars avec chevauchement.

    Un passage doit être assez grand pour être autoporteur (le LLM répond
    à partir d'un seul passage), assez court pour rester pertinent.
    Méta-données : doc, topic, lang (utiles pour filtrer fr/ar à la recherche).
    """
    target = target_chars or config.KB_CHUNK_CHARS
    text = "\n\n".join(p.strip() for p in pages if p and p.strip())
    text = "\n".join(line.strip() for line in text.splitlines())  # normalise
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + target)
        # coupure propre : fin de paragraphe/phrase, jamais en plein mot
        if end < len(text):
            window = text[start + max(0, target - overlap):end + overlap]
            for sep in ("\n\n", ". ", "\n", " "):
                cut = window.rfind(sep)
                if cut >= 0:
                    end = start + max(0, target - overlap) + cut + len(sep)
                    break
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)  # garde le chevauchement

    return [
        {
            "text": c,
            "$vectorize": c,
            "doc": doc,
            "topic": topic,
            "lang": lang,
            "source": source,
        }
        for c in chunks if c
    ]


def ingest(chunks: list[dict]) -> int:
    """insertMany par lots. Retourne le nombre de passages écrits."""
    n = 0
    for i in range(0, len(chunks), INSERT_BATCH):
        _post(f"{_base_url()}/{config.ASTRA_DB_COLLECTION}",
              {"insertMany": {"documents": chunks[i:i + INSERT_BATCH],
                              "options": {"ordered": False}}})
        n += len(chunks[i:i + INSERT_BATCH])
    return n


# ---------------------------------------------------------------------
# Recherche vectorielle ($vectorize : embedding côté Astra)
# ---------------------------------------------------------------------
def search(query: str, lang: str | None = None,
           top_k: int | None = None) -> list[dict]:
    """Retourne les top_k passages pertinents [{text, doc, topic, similarity}].

    Filtre d'abord sur la langue de l'utilisateur, puis retente sans
    filtre si rien trouvé (rareté : une question fr ne doit jamais finir
    en « pas de réponse » faute de passage marqué fr).
    """
    query = (query or "").strip()
    if not query:
        return []
    k = top_k or config.FAQ_TOP_K
    url = f"{_base_url()}/{config.ASTRA_DB_COLLECTION}"

    def _find(filter_doc: dict | None) -> list[dict]:
        options: dict = {"limit": k, "includeSimilarity": True}
        find: dict = {
            "sort": {"$vectorize": query},   # embedding NVIDIA intégré côté Astra
            "options": options,
        }
        if filter_doc:
            find["filter"] = filter_doc
        data = _post(url, {"find": find})
        docs = (data.get("data") or {}).get("documents") or []
        return [{
            "text": d.get("text") or "",
            "doc": d.get("doc") or "",
            "topic": d.get("topic") or "",
            "similarity": float(d.get("$similarity") or 0),
        } for d in docs if d.get("text")]

    hits = _find({"lang": lang} if lang in {"fr", "ar", "en"} else None)
    if not hits and lang:
        hits = _find(None)  # langue absente dans la KB : réponses faibles quand même
    return hits


def format_context(hits: list[dict], max_chars: int | None = None) -> str:
    """Assemble les passages pour le prompt du FAQ agent."""
    budget = max_chars or 6000
    parts: list[str] = []
    used = 0
    for h in hits:
        piece = h["text"].strip()
        tag = f"[{h['doc']}" + (f" · {h['topic']}" if h["topic"] else "") + "]"
        if used + len(piece) > budget and parts:
            break
        parts.append(f"{tag}\n{piece}")
        used += len(piece) + len(tag) + 2
    return "\n\n".join(parts)
