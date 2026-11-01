# =====================================================================
# Contrat commun des scrapers multi-sources (carte soukna-sources-agent).
#
# Un ADAPTER = fonction `fetch(source: dict) -> list[dict]` qui reçoit la
# ligne `sources` de la base (name, base_url, kind, adapter, ...) et
# retourne des opportunités brutes. `normalize()` (ici) garantit ensuite
# la forme attendue par db.upsert_opportunity : clés obligatoires,
# bornage des longueurs, déduction du `opportunity_type`
# (appel d'offres / bon de commande / consultation) et du `source_ref`.
# =====================================================================
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

TYPE_LABELS = {
    "bon_commande": "Bon de commande",
    "consultation": "Consultation",
    "appel_offres": "Appel d'offres",
}


def slugify(name: str) -> str:
    text = unicodedata.normalize("NFKD", (name or "").lower()).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return slug[:24] or "source"


def infer_opportunity_type(title: str, ref: str = "") -> str:
    """Déduction robuste du type à partir du libellé et de la référence."""
    low = (title or "").lower()
    ref_low = (ref or "").lower()
    if "bon" in low and "commande" in low or ref_low.startswith("bc"):
        return "bon_commande"
    if "consultation" in low and "appel" not in low:
        return "consultation"
    return "appel_offres"


def normalize_item(item: dict[str, Any], source_name: str) -> dict[str, Any]:
    """Complète/nettoie une opportunité brute quel que soit le scraper."""
    ref = str(item.get("source_ref") or "").strip()
    if not ref:
        seed = f"{item.get('title', '')}{item.get('url', '')}"
        ref = f"{slugify(source_name)}:{hashlib.sha1(seed.encode()).hexdigest()[:12]}"
    elif not ref.startswith(slugify(source_name) + ":") and ":" not in ref:
        ref = f"{slugify(source_name)}:{ref}"

    title = str(item.get("title") or "").strip()[:250] or "Opportunité sans objet"
    ref_clean = ref.split(":", 1)[-1]
    return {
        "source_ref": ref,
        "source": item.get("source") or slugify(source_name),
        "title": title,
        "buyer": str(item.get("buyer") or "")[:180],
        "city": str(item.get("city") or "")[:80],
        "region": str(item.get("region") or "")[:80],
        "sector": str(item.get("sector") or "")[:60],
        "domain_code": str(item.get("domain_code") or "")[:40],
        "deadline": item.get("deadline"),
        "amount": str(item.get("amount") or "")[:80],
        "url": str(item.get("url") or "")[:400],
        "raw": item.get("raw") or {},
        "opportunity_type": item.get("opportunity_type")
        or infer_opportunity_type(title, ref_clean),
    }
