# =====================================================================
# Opportunités seed — fixtures réalistes (démo, tests hors-ligne, repli
# si le portail est indisponible). Inspirées de la démo de la landing.
# =====================================================================
from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def _deadline(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


SEED_OPPORTUNITIES: list[dict[str, Any]] = [
    {
        "source_ref": "SO-DEM-001",
        "title": "Maintenance et évolution d'une plateforme de gestion",
        "buyer": "Organisme acheteur (démo)",
        "city": "Casablanca",
        "region": "Casablanca",
        "sector": "Informatique",
        "domain_code": "3.19",
        "deadline": _deadline(20),
        "amount": "800 000 - 1 200 000 MAD",
        "url": "",
        "raw": {"note": "seed illustratif"},
    },
    {
        "source_ref": "SO-DEM-002",
        "title": "Réhabilitation d'un bâtiment administratif",
        "buyer": "Collectivité locale (démo)",
        "city": "Rabat",
        "region": "Rabat",
        "sector": "BTP",
        "domain_code": "1.15",
        "deadline": _deadline(23),
        "amount": "3 000 000 - 5 000 000 MAD",
        "url": "",
        "raw": {"note": "seed illustratif"},
    },
    {
        "source_ref": "SO-DEM-003",
        "title": "Fourniture de matériel informatique et périphériques",
        "buyer": "Établissement public (démo)",
        "city": "Tanger",
        "region": "Tanger",
        "sector": "Fournitures",
        "domain_code": "2.18",
        "deadline": _deadline(12),
        "amount": "400 000 - 700 000 MAD",
        "url": "",
        "raw": {"note": "seed illustratif"},
    },
    {
        "source_ref": "SO-DEM-004",
        "title": "Contrat de nettoyage et gardiennage multi-sites",
        "buyer": "Ministère (démo)",
        "city": "Marrakech",
        "region": "Marrakech",
        "sector": "Services et maintenance",
        "domain_code": "3.15",
        "deadline": _deadline(15),
        "amount": "1 000 000 - 2 000 000 MAD",
        "url": "",
        "raw": {"note": "seed illustratif"},
    },
    {
        "source_ref": "SO-DEM-005",
        "title": "Étude d'ingénierie pour l'extension d'un réseau d'eau",
        "buyer": "Régie régionale (démo)",
        "city": "Agadir",
        "region": "Agadir",
        "sector": "Conseil et études",
        "domain_code": "3.10",
        "deadline": _deadline(30),
        "amount": "500 000 - 900 000 MAD",
        "url": "",
        "raw": {"note": "seed illustratif"},
    },
    {
        "source_ref": "SO-DEM-006",
        "title": "Audit et accompagnement à la transformation numérique",
        "buyer": "Entreprise publique (démo)",
        "city": "Casablanca",
        "region": "Casablanca",
        "sector": "Conseil et études",
        "domain_code": "3.11",
        "deadline": _deadline(18),
        "amount": "600 000 - 1 000 000 MAD",
        "url": "",
        "raw": {"note": "seed illustratif"},
    },
    {
        "source_ref": "SO-DEM-007",
        "title": "Maintenance informatique multi-sites (parc bureautique)",
        "buyer": "Direction régionale (démo)",
        "city": "Rabat",
        "region": "Rabat",
        "sector": "Informatique",
        "domain_code": "3.19",
        "deadline": _deadline(21),
        "amount": "300 000 - 600 000 MAD",
        "url": "",
        "raw": {"note": "seed illustratif"},
    },
    {
        "source_ref": "SO-DEM-008",
        "title": "Fourniture de mobilier de bureau et équipements",
        "buyer": "Université (démo)",
        "city": "Marrakech",
        "region": "Marrakech",
        "sector": "Fournitures",
        "domain_code": "2.19",
        "deadline": _deadline(25),
        "amount": "200 000 - 450 000 MAD",
        "url": "",
        "raw": {"note": "seed illustratif"},
    },
]
