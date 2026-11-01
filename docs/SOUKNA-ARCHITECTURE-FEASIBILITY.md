# SOUKNA — Architecture Feasibility Assessment
Date: 2026-11-02 · Author: senior review (repository-verified, not theoretical)
Companion docs: `SOUKNA-PROPOSED-DATA-MODEL.md`, `SOUKNA-IMPLEMENTATION-ROADMAP.md`,
live-source evidence: `AUDIT-portail-marchespublics.md`.

## 1. What actually exists in the repository (verified this session)

### Collection
- `soukna_graph/tools/portal.py`: PRADO quick search (10 results/term, no
  pagination), + `advanced_search()` walker. **Pagination root-caused and
  fixed** (CONTENU_PAGE underscore corruption): 12 consecutive pages,
  0 repeats, 84 unique refs verified live. Criteria verified working
  (keywordSearch: 10/10 relevance). **Date filters verified NOT applied**
  without keywords (two disjoint windows → identical results).
- `soukna_graph/tools/scrapers/`: `base.py` (normalize, type inference),
  `marchespublics.py` (wrapper + expired filter), `generic_rss.py` (RSS).
- `nodes/sources.py`: multi-source registry walker (table `sources`,
  admin-managed, per-source status) + 30-keyword quick search + seed fallback.
- Portal sections mapped: `annonceType` 2/4/5/6/8/9 (information,
  **résultat définitif**, extrait PV, rapport achèvement, **résiliation**,
  rapport présentation), `procedureType` (20), `categorie`
  (Travaux/Fournitures/Services). **Bons de commande section: not located.**
- Limits verified live: date filter NOT applied without keywords;
  10 items/page; unfiltered listing sorted by end-of-display (PV far-future
  first — unfavorable); no JSON API; no pagination on quick search.

### Database (Supabase, 16 tables, RLS)
- `opportunities`: source_ref UNIQUE (dedup key), title, buyer, city/region,
  sector, domain_code, deadline, amount, url, raw JSONB, opportunity_type,
  created_at/updated_at (**collection timestamps only — no published_at**),
  **no lifecycle status column** (the `verdict` field is LLM advice
  go/a_etudier/no_go — not procurement status).
- `matches`: per-company LLM scoring (0-100), verdict, risks, saved/status
  (kanban), note. **No recommendation history or match audit.**
- `pipeline_runs`: per-run counters. **No page-level collection logs.**
- No `procurements` (operation) entity: each announcement row IS the record;
  lifecycle announcements (award/cancel) are **not linked** to the original.
- `sources`, `sectors` (18 seeded), `chat_messages`, `users`, `waitlist`,
  `invite_tokens`, `audit_log`, `monitor_state`, `lg_*`.

### Backend
- ~40 endpoints: /run, /opportunities (min_score/type/sector/city),
  /observability*, /monitoring/report, /admin/sources CRUD+test, /profile,
  /admin/waitlist*, /onboarding, HMAC auth (admin/entreprise).
- Matching runs inside the daily pipeline (batch per company) + chat.
- Scheduler: GitHub workflow + local schtasks (`run_scheduled.py`);
  no distributed-lock on concurrent runs (single-instance deployment).

### Frontend
- Dashboard: kanban, sector/city/verdict/type filters, drawer, profile
  (extended fields), digests history. **No 24 h / 7 d / historical views.**
- Admin console 5 tabs (finances, agents, logs, monitoring, sources).

### Infrastructure
- Render (workflow Docker + dashboard), Supabase, GHCR CI/CD with deploy
  hooks, Brevo email, WhatsApp Cloud API, monitoring agent (7 checks).

## 2. Feasibility table

| Component | Current state | Feasibility | Required changes | Risks |
|---|---|---|---|---|
| Keyword discovery (30 terms) | IMPLEMENTED | KEEP as secondary | none | misses non-matching titles |
| Section walkers (annonceType 2/4/5/6/8/9) | PARTIALLY (walker exists; sections mapped; pagination verified on type 4) | FEASIBLE | per-section configs; verify each filter by ref-comparison | portal filter may silently not apply — verify per section |
| Unfiltered bounded walk | PARTIALLY (walker works unfiltered; 239 785 items, sort unfavorable) | FEASIBLE (bounded) | page-window budget, stop rules | low signal density per page |
| Date-window incremental | BLOCKED (portal ignores date criteria) | REQUIRES CHANGES | crack hidden criteria panel; else daily section re-walk as proxy | may stay blocked indefinitely |
| Bons de commande discovery | NOT VERIFIED | BLOCKED until section located | find listing route; then adapter | may not exist as separate section |
| Lifecycle linkage (award/cancel ↔ original) | REQUIRES CHANGES | FEASIBLE | refs are stable (`refXXXXXX` family reused across announcement types) — link by normalized ref family + buyer | some refs differ per announcement — evidence needed |
| Status model (ACTIVE/EXPIRED/AWARDED/CANCELLED/UNKNOWN) | REQUIRES CHANGES | FEASIBLE | `status` column + official evidence via annonceType sections; EXPIRED from deadline (safe); never infer award/cancel from deadline | portal evidence incomplete for some notices → UNKNOWN |
| `published_at` vs collection timestamps | REQUIRES CHANGES | PARTIALLY (listing lacks publication date; detail pages may expose it) | extract from detail pages; else first_seen/last_seen only | detail-page visits multiply requests |
| Initial historical collection | FEASIBLE (bounded by portal) | FEASIBLE with budget | resume cursor (page offset persisted), incremental upserts | 10/page × 239 785 ≈ 24 000 pages full walk (days of polite fetching) → bound it |
| Collection run logs (page-level) | REQUIRES CHANGES | FEASIBLE | `collection_runs` + `collection_pages` tables | none |
| Central DB serving all companies | IMPLEMENTED (already the design) | KEEP | none | none |
| Matching AFTER central collection | IMPLEMENTED (pipeline order) | KEEP | decouple per-company re-matching on profile change | LLM cost grows with companies |
| Explainable recommendations | PARTIALLY (reasons[] from LLM) | FEASIBLE | structured rule-based reasons + history signals | LLM reasons are non-deterministic |
| 24 h / 7 d views | BLOCKED for official publication date (no published_at) | PARTIAL | use first_seen as proxy, clearly labelled; add published_at when extractable | mislabeling risk |
| Historical archive view | FEASIBLE (status + filters) | FEASIBLE | status column + UI section | none |
| Scale (companies × records) | FEASIBLE | FEASIBLE | indexes (matches company+score), per-company match jobs queued | LLM cost per company per run |

## 3. Explicit answers

1. **Central historical DB?** YES — technically feasible (verified walker +
   upsert + dedup). Bounded by portal: 10/page, unfavorable sort, no date
   filter → full mirror infeasible; bounded historical walk feasible.
2. **Collect without primary keywords?** PARTIALLY — verified: section
   walkers (annonceType) + bounded unfiltered walk. Verified INFEASIBLE:
   date-window incremental (portal ignores dates). Keywords remain the
   most precise discovery tool → hybrid, not keyword-free.
3. **Daily incremental reliable?** NOT YET — no working date filter.
   Reliable alternative: daily re-walk of section page-1..N (N≈10-30)
   where recent announcements concentrate (verified present) + dedup.
4. **Update old records on change?** YES — re-encounter upserts exist;
   needs reconciliation walkers (annonceType=4/8) + status transitions.
5. **Link award/cancel to original?** YES, evidence-based: normalized
   official ref family + buyer (verified refs stable `refXXXXXX`);
   unknown-notice fallback via title similarity (never auto).
6. **published_at vs collected_at?** NOT YET — collection timestamps exist;
   publication date absent from listings; verify detail pages; else use
   first_seen labelled honestly.
7. **24 h view?** Only via first_seen (collection-based) today; true
   publication-date view BLOCKED until published_at extraction works.
8. **All currently available (incl. older)?** YES — status=ACTIVE filter
   (deadline ≥ today, not cancelled/awarded) over central DB.
9. **Preserve expired/awarded/cancelled?** YES — never delete (upserts);
   status column + history.
10. **Historical data improves recommendations?** YES — buyers, categories,
    regions, recurring patterns (rule-based phase 2). Do NOT claim win-
    probability prediction without large clean data.
11. **Scale?** YES — Supabase + indexes; LLM cost is the scaling limit
    (batching, caching per opportunity×profile signature).

## 4. Implementation percentage (component-weighted, justified)

Weights: collection 35 %, DB model 25 %, matching/reco 20 %, user views
15 %, infra/ops 5 %.
- Collection: sections walkers working (25/35 of collection sub-scope done,
  no-keyword primary partial, BC missing, incremental blocked) ≈ 45 %
- DB model: current tables ≈ 30 % of target model
- Matching: current ≈ 50 %
- Views: ≈ 35 %
- Infra/ops: ≈ 85 %
**Weighted overall ≈ 40–45 % implemented.** (Explicit per-component basis;
not a precise science.)

## 5. Three biggest blockers

1. **Portal date filtering broken** → no true incremental collection;
   workaround = daily bounded section re-walks + dedup.
2. **No published_at in listings** → "24 h" views must start from
   first_seen until detail-page extraction proves feasible.
3. **Bons de commande section unlocated** → dedicated BC collector blocked.

## 6. Implement first / avoid prematurely

- FIRST: status model + section walkers + lifecycle linkage + run logs
  (they unblock everything else, cheap, verified mechanics).
- AVOID: full 239 785-record mirror; win-probability predictions;
  Playwright fleet for WAF sites; per-company collection.

## 7. Expected platform limitations (permanent, portal-imposed)

- 10 items/page → polite bounded walks, never full mirror.
- No date filter (unless hidden panel cracked) → "new" = re-encounter.
- Section filters must be re-verified per section (silent no-op risk).
- Detail pages needed for published_at and richer fields (request budget).
- Sources beyond the portal (ONDA/OCP WAF, JS sites) need Playwright-class
  collectors — separate phase.
