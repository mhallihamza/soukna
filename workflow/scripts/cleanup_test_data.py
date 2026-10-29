# =====================================================================
# cleanup_test_data.py — purge des données de test (prefixe eval-).
# À lancer après une session de tests manuels ou avant une démo.
# =====================================================================
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import cleanup_test_data, ensure_db  # noqa: E402


def main() -> None:
    ensure_db()
    deleted = cleanup_test_data()
    print("Purge des données de test :")
    for table, count in deleted.items():
        print(f"  {table:20} {count} ligne(s) supprimée(s)")


if __name__ == "__main__":
    main()
