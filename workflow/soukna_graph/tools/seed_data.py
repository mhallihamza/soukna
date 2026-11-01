# =====================================================================
# Opportunités seed — fixtures réalistes (démo, tests hors-ligne, repli
# si le portail est indisponible). Inspirées de la démo de la landing.
# =====================================================================
from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def _deadline(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


# Référentiel secteurs — couverture réaliste des achats publics marocains.
# Seed au démarrage (db.sectors_ensure) ; utilisé par l'onboarding, la
# console, le matching et le mapping des domain_code des portails.
SECTORS: list[dict[str, str]] = [
    {"code": "informatique", "label_fr": "Informatique & numérique", "label_ar": "المعلوميات والرقمنة", "category": "services"},
    {"code": "travaux", "label_fr": "Travaux & BTP", "label_ar": "الأشغال والبناء", "category": "travaux"},
    {"code": "fournitures", "label_fr": "Fournitures & équipements", "label_ar": "التوريدات والتجهيزات", "category": "fournitures"},
    {"code": "mobilier", "label_fr": "Mobilier & aménagement", "label_ar": "الأثاث والتجهيز", "category": "fournitures"},
    {"code": "maintenance", "label_fr": "Maintenance & entretien", "label_ar": "الصيانة", "category": "services"},
    {"code": "etudes", "label_fr": "Études & conseil", "label_ar": "الدراسات والاستشارة", "category": "services"},
    {"code": "formation", "label_fr": "Formation", "label_ar": "التكوين", "category": "services"},
    {"code": "gardiennage", "label_fr": "Gardiennage & sécurité privée", "label_ar": "الحراسة والأمن الخاص", "category": "services"},
    {"code": "nettoyage", "label_fr": "Nettoyage & propreté", "label_ar": "النظافة", "category": "services"},
    {"code": "transport", "label_fr": "Transport & logistique", "label_ar": "النقل واللوجستيك", "category": "services"},
    {"code": "energie", "label_fr": "Énergie & électricité", "label_ar": "الطاقة والكهرباء", "category": "technique"},
    {"code": "eau", "label_fr": "Eau & assainissement", "label_ar": "الماء والصرف الصحي", "category": "technique"},
    {"code": "sante", "label_fr": "Santé & équipements médicaux", "label_ar": "الصحة والتجهيزات الطبية", "category": "fournitures"},
    {"code": "agroalimentaire", "label_fr": "Agroalimentaire", "label_ar": "الصناعة الغذائية", "category": "fournitures"},
    {"code": "impression", "label_fr": "Impression & communication", "label_ar": "الطباعة والتواصل", "category": "services"},
    {"code": "telecom", "label_fr": "Télécoms", "label_ar": "الاتصالات", "category": "technique"},
    {"code": "hydrocarbures", "label_fr": "Hydrocarbures & chimie", "label_ar": "المحروقات والكيمياء", "category": "fournitures"},
    {"code": "environnement", "label_fr": "Environnement & déchets", "label_ar": "البيئة والنفايات", "category": "services"},
]

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
