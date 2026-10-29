# =====================================================================
# apply_schema.py — crée/migre toutes les tables Soukna sur la base
# pointée par DATABASE_URL (Supabase ou Postgres local).
#
#   py workflow/scripts/apply_schema.py            # .env du workflow
#   py workflow/scripts/apply_schema.py --url postgresql://...
#
# Le script exécute docs/supabase_schema.sql (idempotent) puis affiche
# les tables présentes pour vérification.
# =====================================================================
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from soukna_graph import config, db  # noqa: E402

SCHEMA_FILE = Path(__file__).resolve().parents[2] / "docs" / "supabase_schema.sql"


def main() -> int:
    parser = argparse.ArgumentParser(description="Applique le schéma Soukna")
    parser.add_argument(
        "--url",
        default="",
        help="Connection string Postgres (défaut : DATABASE_URL du .env)",
    )
    args = parser.parse_args()

    if args.url:
        config.DATABASE_URL = args.url
        db._pool = None  # force un nouveau pool sur l'URL fournie

    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    print(f"[soukna] base   : {config.DATABASE_URL.split('@')[-1]}")
    print(f"[soukna] schéma : {SCHEMA_FILE.name} ({len(sql)} caractères)")

    conn = db.connect()
    try:
        conn.execute(sql)
    finally:
        db.putconn(conn)

    tables = db.query(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' ORDER BY table_name"
    )
    print(f"[soukna] OK — {len(tables)} tables :")
    for row in tables:
        print(f"  - {row['table_name']}")
    if db._pool is not None:
        db._pool.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
