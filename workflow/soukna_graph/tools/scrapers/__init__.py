# =====================================================================
# Registre des adaptateurs multi-sources (carte soukna-sources-agent).
# Ajouter une nouvelle famille de site = un module ici + une entrée
# dans ADAPTERS. L'activation/la configuration, elles, se font depuis
# la console admin (table sources) sans redéploiement.
# =====================================================================
from __future__ import annotations

from typing import Callable

from . import generic_rss, marchespublics

ADAPTERS: dict[str, Callable[[dict], list[dict]]] = {
    "marchespublics": marchespublics.fetch,
    "generic_rss": generic_rss.fetch,
}


def get_adapter(name: str) -> Callable[[dict], list[dict]] | None:
    return ADAPTERS.get((name or "").strip())
