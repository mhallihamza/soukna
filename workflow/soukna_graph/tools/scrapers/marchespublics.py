# =====================================================================
# Adaptateur du portail national marchespublics.gov.ma : délègue au
# module historique portal.py (logique PRADO validée en live), filtre
# les opportunités EXPIRÉES (on ne surveille que le vivier actionnable)
# et normalise au contrat commun multi-sources.
# =====================================================================
from __future__ import annotations

from datetime import date

from .. import portal
from .base import normalize_item


def fetch(source: dict) -> list[dict]:
    """Recherche rapide par secteur sur le portail national.

    `source` n'apporte pas l'URL (le module historique utilise
    config.PORTAL_BASE) ; il porte le nom/la cadence pour la console.
    """
    items = portal.fetch_consultations()
    today = date.today().isoformat()
    name = source.get("name") or "portal"
    out = []
    for item in items:
        dl = item.get("deadline")
        if dl and dl < today:
            continue  # échéance dépassée : pas actionable, on saute
        out.append(normalize_item(item, name))
    return out
