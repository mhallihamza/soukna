# SOUKNA — Proposed Data Model (based on the verified existing schema)
Companion: `SOUKNA-ARCHITECTURE-FEASIBILITY.md`. Reuses/extends existing
tables; adds only what the lifecycle model requires. No destructive changes.

## 1. Existing (verified) — kept as-is or lightly extended

- `companies` (profiles incl. extended fields) · `users` · `waitlist` ·
  `invite_tokens` · `audit_log` · `digests` · `matches` · `pipeline_runs` ·
  `lg_requests`/`lg_logs` · `monitor_state` · `sources` · `sectors` ·
  `chat_messages`.

## 2. Extensions to existing tables

### `opportunities` (the official ANNOUNCEMENT record — one row per official notice)
```sql
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS status TEXT
  NOT NULL DEFAULT 'ACTIVE';      -- ACTIVE|EXPIRED|AWARDED|CANCELLED|UNKNOWN
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS status_evidence TEXT;
  -- 'annonceType=4' | 'annonceType=8' | 'deadline' | null(=UNKNOWN)
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;
  -- extraction pending (detail pages); NULL = unknown, never faked
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMPTZ
  NOT NULL DEFAULT now();
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ
  NOT NULL DEFAULT now();
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS proc_family TEXT;
  -- normalized reference family linking lifecycle announcements
CREATE INDEX IF NOT EXISTS idx_opportunities_status ON opportunities(status);
CREATE INDEX IF NOT EXISTS idx_opportunities_family ON opportunities(proc_family);
CREATE INDEX IF NOT EXISTS idx_opportunities_type ON opportunities(opportunity_type);
```
- `first_seen_at` = first collection (proxy for publication date, clearly
  labelled in UI until `published_at` extraction is proven).
- `last_seen_at` = re-encounter timestamp (reconciliation evidence).

### `matches` — add match history (recommendations without losing history)
```sql
ALTER TABLE matches ADD COLUMN IF NOT EXISTS reasons_rule JSONB DEFAULT '[]';
ALTER TABLE matches ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_matches_company_score ON matches(company_id, match_score DESC);
```

## 3. New tables

### `procurements` — the underlying procurement OPERATION (optional but recommended)
One row per logical procurement; several announcements reference it.
```sql
CREATE TABLE IF NOT EXISTS procurements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_key TEXT UNIQUE NOT NULL,       -- normalized ref family + buyer hash
    title TEXT NOT NULL,
    buyer TEXT,
    city TEXT, region TEXT,
    sector TEXT, categorie TEXT,
    current_status TEXT NOT NULL DEFAULT 'UNKNOWN',
    opened_at TIMESTAMPTZ,                 -- earliest announcement
    closed_at TIMESTAMPTZ,                 -- earliest deadline seen
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS procurement_id UUID
  REFERENCES procurements(id);
CREATE INDEX IF NOT EXISTS idx_opportunities_procurement ON opportunities(procurement_id);
```
Family key derivation (verified stable on the portal): normalized official
reference `refXXXXXX` + buyer lower/trims; `22/2026/OMPIC` appears across
announcement types with the same `ref` core. Unknown-family announcements
(award/cancel whose original was never seen) create their own
`procurements` row with status AWARDED/CANCELLED — no silent guessing.

### `collection_runs` — page-level collection evidence (replaces/augments pipeline_runs)
```sql
CREATE TABLE IF NOT EXISTS collection_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    kind TEXT NOT NULL,                    -- initial|incremental|reconcile
    sections TEXT[],                       -- e.g. {ao,bc,resultats,resiliation}
    pages_attempted INT, pages_unique INT, pages_repeated INT, pages_empty INT,
    raw_records INT, unique_records INT, new_records INT, dup_records INT,
    updated_records INT, rejected_records INT,
    errors INT,
    complete BOOLEAN,                      -- last page reached per section?
    notes TEXT
);
```

### `procurement_events` — status/lifecycle history (append-only)
```sql
CREATE TABLE IF NOT EXISTS procurement_events (
    id BIGSERIAL PRIMARY KEY,
    opportunity_id UUID REFERENCES opportunities(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,        -- published|extended|awarded|cancelled|expired|seen
    evidence TEXT,                   -- 'annonceType=8' | 'deadline<today' | null
    source_ref TEXT,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pevents_opportunity ON procurement_events(opportunity_id, observed_at DESC);
```
Status changes = new event + `opportunities.status` update; history never
overwritten (append-only), satisfying "record changes without losing history".

## 4. Duplicate & multi-announcement rules
- Announcement uniqueness: `opportunities.source_ref` UNIQUE (official ref +
  source prefix) — unchanged, verified across keyword searches and pages.
- Same announcement seen again: `last_seen_at` update only (no new row).
- Lifecycle announcements: separate rows (different official refs), linked
  via `proc_family` → one `procurements` row; dashboards count
  `procurements` (or `opportunities WHERE status='ACTIVE'`), never raw
  announcements, so a tender + its award ≠ 2 opportunities.
- Cross-collector duplicates: same source_ref from keyword vs section
  collectors → upsert merge (non-null wins), first_seen preserved.

## 5. Status lifecycle (evidence rules)
| Status | Evidence required |
|---|---|
| ACTIVE | deadline ≥ today AND no official cancel/award evidence |
| EXPIRED | deadline < today AND no official award/cancel evidence |
| AWARDED | row from annonceType=4 walk linked to family |
| CANCELLED | row from annonceType=8 walk linked to family |
| UNKNOWN | contradictory evidence (e.g., result after resiliation) |
Transitions recorded as `procurement_events`; recompute order: official
evidence first, deadline only fills the gap.

## 6. Views (same central DB)
- 24 h / 7 d: `WHERE first_seen_at > now()-interval` until `published_at`
  extraction is proven (UI label: "Nouvelles collectes" vs "Publiées").
- Currently available: `status='ACTIVE'`.
- Historical: `status IN ('EXPIRED','AWARDED','CANCELLED')`.
- Recommended: from `matches` (+ rule reasons), joined to ACTIVE set.

## 7. What is deliberately NOT added
- No `company_collections` (one central DB serves all companies).
- No full historical mirror table (bounded walks only).
- No ML tables (phase 3 only, if data justifies).
