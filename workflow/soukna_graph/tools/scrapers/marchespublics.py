# =====================================================================
# Adaptateur du portail national marchespublics.gov.ma : délègue au
# module historique portal.py (logique PRADO validée en live) et
# normalise les items au contrat commun multi-sources.
# =====================================================================
from __future__ import annotations

from .. import portal
from .base import normalize_item


def fetch(source: dict) -> list[dict]:
    """Recherche rapide par secteur sur le portail national.

    `source` n'apporte pas l'URL (le module historique utilise
    config.PORTAL_BASE) ; il porte le nom/la cadence pour la console.
    """
    items = portal.fetch_consultations()
    name = source.get("name") or "portal"
    return [normalize_item(item, name) for item in items]
