# =====================================================================
# Garde-fou de la suite hors-ligne : aucun test ne doit contacter une
# vraie base. Toute tentative de connexion échoue immédiatement avec un
# message explicite (au lieu des 30 s de retries du pool en CI, ou pire,
# d'une connexion silencieuse à Supabase depuis le poste de dev).
# Les tests qui ont besoin de données monkeypatchent db.* localement.
# =====================================================================
import pytest

from soukna_graph import db


@pytest.fixture(autouse=True)
def no_database(monkeypatch):
    def _forbidden(*args, **kwargs):
        raise RuntimeError("DB interdite dans les tests hors-ligne — monkeypatcher db.*")

    monkeypatch.setattr(db, "connect", _forbidden)
