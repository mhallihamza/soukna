# =====================================================================
# load_kb.py — ingère les PDF de la base de connaissances (kb/) dans la
# collection Astra « souknabase » avec l'embedding INTÉGRÉ (champ
# $vectorize, service NVIDIA) : aucun appel d'embedding externe.
#
#   py scripts/load_kb.py            # ingestion complète
#   py scripts/load_kb.py --lang fr  # une seule langue
#   py scripts/load_kb.py --dry-run  # découpage sans écriture
#
# Ré-ingestion sûre : les passages d'un document déjà en base sont
# supprimés avant réécriture (pas de doublons à chaque run).
# =====================================================================
from __future__ import annotations

import argparse
import sys

sys.path.insert(0, ".")

from soukna_graph import config  # noqa: E402
from soukna_graph.tools import astra_kb  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingestion de la base de connaissances FAQ dans Astra")
    parser.add_argument("--lang", choices=["fr", "ar"], default=None,
                        help="limiter à une langue (ex. --lang fr)")
    parser.add_argument("--dry-run", action="store_true",
                        help="afficher le découpage sans écrire dans Astra")
    args = parser.parse_args()

    if not args.dry_run:
        if not config.astra_ready():
            print("ASTRA_DB_API_ENDPOINT / ASTRA_DB_TOKEN manquants dans .env",
                  file=sys.stderr)
            return 1

    pdfs = sorted((config.KB_DIR).glob("soukna-kb-*.pdf")) if config.KB_DIR.exists() else []
    if args.lang:
        pdfs = [p for p in pdfs if p.stem.endswith(f"-{args.lang}")]
    if not pdfs:
        print(f"aucun PDF dans {config.KB_DIR}", file=sys.stderr)
        return 1

    total = 0
    for pdf in pdfs:
        from pypdf import PdfReader  # import local : le CLI reste utilisable hors ingestion

        reader = PdfReader(str(pdf))
        pages = [page.extract_text() or "" for page in reader.pages]

        stem = pdf.stem  # ex. soukna-kb-02-tarifs-fr
        topic = stem.split("-")[3] if len(stem.split("-")) > 3 else ""
        lang = stem.rsplit("-", 1)[-1]
        chunks = astra_kb.chunk_pages(pages, doc=stem, topic=topic, lang=lang,
                                      source=f"kb/{pdf.name}")
        print(f"{pdf.name} : {len(pages)} pages → {len(chunks)} passages")
        total += len(chunks)
        if not args.dry_run and chunks:
            astra_kb.ensure_collection()
            deleted = astra_kb.delete_source([stem])
            written = astra_kb.ingest(chunks)
            if deleted:
                print(f"  ré-ingestion : {deleted} anciens passages supprimés")
            print(f"  → {written} passages écrits dans « {config.ASTRA_DB_COLLECTION} »")

    if not args.dry_run:
        print(f"\nTerminé : {astra_kb.count_documents()} passages au total "
              f"dans « {config.ASTRA_DB_COLLECTION} ».")
    else:
        print(f"\n(dry-run : {total} passages n'ont PAS été écrits)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
