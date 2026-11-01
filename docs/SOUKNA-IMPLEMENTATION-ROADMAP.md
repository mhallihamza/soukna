# SOUKNA — Implementation Roadmap (assessment-verified)
Companion docs: `SOUKNA-ARCHITECTURE-FEASIBILITY.md`, `SOUKNA-PROPOSED-DATA-MODEL.md`,
live evidence: `AUDIT-portail-marchespublics.md`.

## Phase 0 — Status & evidence foundations (1-2 days)
- DB migration: `opportunities.status/status_evidence/first_seen_at/last_seen_at/proc_family`
  + `collection_runs` + `procurement_events` (+ procurements optional).
- Status compute: ACTIVE/EXPIRED from deadline; AWARDED/CANCELLED only via
  official sections; UNKNOWN otherwise. Append events on transitions.
- Backfill existing rows (status by deadline rule; first_seen = created_at).
- Files: `soukna_graph/db.py`, `docs/supabase_schema.sql`, `nodes/sources.py`.
- Tests: status rules, event append, idempotent backfill.
- Acceptance: every row has a status + evidence; re-run changes nothing.

## Phase 1 — Section collectors (2-3 days)
- `advanced_search(annonce_type=4|8|2|5|6|9)` section walkers (walker
  already reliable: 12 pages/0 repeats verified).
- **Gate**: per-section filter verification by ref-comparison against the
  unfiltered list (silent no-op risk documented) — a section that fails
  verification is marked UNAVAILABLE in `collection_runs`, not faked.
- Bons de commande: locate section (portal nav sweep + procedureType full
  list) — if unlocatable, documented as limitation, quick-search terms
  keep partial BC coverage.
- Files: `portal.py`, `scrapers/marchespublics.py`, `nodes/sources.py`.
- Tests: walker page-count/repeat/retry (mocked), live section probes.
- Acceptance: per-section unique counts recorded in `collection_runs`
  with complete/incomplete flags.

## Phase 2 — Hybrid daily collector (1-2 days)
- Primary: section walks (bounded: type=4/8 pages 1-10, information 1-20).
- Secondary: 30 keywords (unchanged).
- Reconciliation: re-encounters update `last_seen_at` + statuses; dedup by
  source_ref; family linkage → procurements.
- Concurrency guard: single-instance lock (DB advisory lock) to prevent
  overlapping runs.
- Files: `nodes/sources.py`, `portal.py`, `api.py` (run endpoint reports).
- Acceptance: two consecutive runs → run 2 produces 0 new duplicates.

## Phase 3 — User views (1-2 days)
- API: `/opportunities?view=24h|7d|active|history` (+ existing filters).
- Dashboard: segmented tabs (Nouvelles collectes 24 h/7 j — labelled
  collection-based until published_at exists —, Disponibles, Historique
  with status badges), BC/type badges already present.
- Acceptance: no expired/awarded/cancelled notice shown as actionable.

## Phase 4 — Recommendation upgrades (progressive)
- Phase 1 rules: sector/city/budget/qualification scoring as structured
  `reasons_rule` (explainable), LLM as enrichment.
- Phase 2 history: recurring buyers/categories/regions per company
  (requires ≥ 30 days of collected data).
- Phase 3: similarity/awards patterns — only with clean data; never claim
  win-probability without evidence.
- Measure: precision spot-checks by the admin on sampled recommendations.

## Dependencies & order
0 → 1 → 2 → 3 → 4 (each phase independently deployable; collection never
breaks: keyword fallback preserved at every step).

## Top risks
1. Section filters may silently no-op → ref-comparison gate mandatory.
2. Publication date unextractable → "24 h" view stays collection-based.
3. BC section may not exist as separate listing → partial coverage.
4. LLM matching cost scales with companies × opportunities → batching +
   pre-filter by rules before LLM.

## Explicitly deferred
Full 239 785-record mirror (portal-infeasible), win-probability ML,
Playwright WAF collectors (ONDA/OCP), per-company collection.
