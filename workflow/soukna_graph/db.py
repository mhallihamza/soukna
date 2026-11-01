# =====================================================================
# Accès Postgres/Supabase : pool simple + schéma (lg_* = observabilité).
# init_db() crée les tables si absentes (utile en local) ; en Supabase,
# exécuter docs/supabase_schema.sql (équivalent) depuis le SQL editor.
# =====================================================================
from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from . import config

_pool: ConnectionPool | None = None


def connect() -> psycopg.Connection:
    """Connexion compatible pooler transactionnel Supabase (pgbouncer)."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            config.DATABASE_URL, min_size=2, max_size=10,
            open=True,
            kwargs={"autocommit": True, "prepare_threshold": None, "row_factory": dict_row},
        )
    return _pool.getconn()


def putconn(conn: psycopg.Connection) -> None:
    if _pool is not None:
        _pool.putconn(conn)


def query(sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
    conn = connect()
    try:
        # None (et non ()) quand aucun paramètre : psycopg3 ignore alors la
        # validation des placeholders — un % littéral (ex. LIKE 'eval-%')
        # lève sinon "only '%s', '%b', '%t' are allowed as placeholders".
        return conn.execute(sql, params or None).fetchall()
    finally:
        putconn(conn)


def execute(sql: str, params: tuple | list = ()) -> int:
    conn = connect()
    try:
        cur = conn.execute(sql, params or None)
        return cur.rowcount
    finally:
        putconn(conn)


SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    phone TEXT UNIQUE,
    password_hash TEXT,
    sectors TEXT[] DEFAULT '{}',
    keywords TEXT[] DEFAULT '{}',
    regions TEXT[] DEFAULT '{}',
    size TEXT DEFAULT 'pme',
    channel_whatsapp BOOLEAN NOT NULL DEFAULT FALSE,
    channel_email BOOLEAN NOT NULL DEFAULT FALSE,
    max_guarantee INT,
    alert_min_score INT NOT NULL DEFAULT 70,
    plan TEXT NOT NULL DEFAULT 'decouverte',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_ref TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL DEFAULT 'seed',
    title TEXT NOT NULL,
    buyer TEXT,
    city TEXT,
    region TEXT,
    sector TEXT,
    domain_code TEXT,
    deadline DATE,
    amount TEXT,
    url TEXT,
    raw JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opportunity_id UUID NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    match_score INT NOT NULL DEFAULT 0,
    reasons JSONB DEFAULT '[]',
    verdict TEXT,
    risks JSONB DEFAULT '[]',
    breakdown JSONB DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'new',
    saved BOOLEAN NOT NULL DEFAULT FALSE,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (opportunity_id, company_id)
);
CREATE TABLE IF NOT EXISTS digests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    digest_date DATE NOT NULL,
    content TEXT NOT NULL,
    channels JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, digest_date)
);
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    source_mode TEXT,
    ingested INT DEFAULT 0,
    matched INT DEFAULT 0,
    verdicted INT DEFAULT 0,
    digests INT DEFAULT 0,
    status TEXT DEFAULT 'running',
    error TEXT
);
CREATE TABLE IF NOT EXISTS lg_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id TEXT,
    sender_phone TEXT,
    route TEXT,
    outcome TEXT,
    error TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    latency_ms INT
);
CREATE TABLE IF NOT EXISTS lg_logs (
    id BIGSERIAL PRIMARY KEY,
    request_id UUID REFERENCES lg_requests(id) ON DELETE CASCADE,
    agent TEXT NOT NULL,
    duration_s NUMERIC(8, 3),
    detail TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS lg_messages_seen (
    message_id TEXT PRIMARY KEY,
    seen_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS monitor_state (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'portal_html',   -- portal_html | rss | api_json
    adapter TEXT NOT NULL DEFAULT 'marchespublics',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    cadence_hours INT NOT NULL DEFAULT 24,
    last_run_at TIMESTAMPTZ,
    last_status TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS sectors (
    code TEXT PRIMARY KEY,
    label_fr TEXT NOT NULL,
    label_ar TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'services',
    enabled BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE IF NOT EXISTS chat_messages (
    id BIGSERIAL PRIMARY KEY,
    phone TEXT NOT NULL,
    role TEXT NOT NULL,                          -- user | assistant
    content TEXT NOT NULL,
    intent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'admin',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS waitlist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    whatsapp TEXT,
    sector TEXT,
    company_size TEXT,
    lang TEXT DEFAULT 'fr',
    consent BOOLEAN NOT NULL DEFAULT TRUE,
    source TEXT,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | invited | active | rejected
    invited_at TIMESTAMPTZ,
    invited_by TEXT,
    activated_at TIMESTAMPTZ,
    admin_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS invite_tokens (
    token TEXT PRIMARY KEY,
    waitlist_id UUID NOT NULL REFERENCES waitlist(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    waitlist_id UUID,
    detail TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

# Colonnes ajoutées après coup : idempotent sur une base déjà déployée.
MIGRATIONS = """
ALTER TABLE companies ADD COLUMN IF NOT EXISTS max_guarantee INT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS alert_min_score INT NOT NULL DEFAULT 70;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS plan TEXT NOT NULL DEFAULT 'decouverte';
ALTER TABLE companies ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active';
ALTER TABLE companies ADD COLUMN IF NOT EXISTS lang TEXT DEFAULT 'fr';
ALTER TABLE companies ADD COLUMN IF NOT EXISTS owner_email TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS waitlist_id UUID;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS trial_started_at TIMESTAMPTZ;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMPTZ;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS breakdown JSONB DEFAULT '{}';
ALTER TABLE matches ADD COLUMN IF NOT EXISTS saved BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS note TEXT;
ALTER TABLE waitlist ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE waitlist ADD COLUMN IF NOT EXISTS invited_at TIMESTAMPTZ;
ALTER TABLE waitlist ADD COLUMN IF NOT EXISTS invited_by TEXT;
ALTER TABLE waitlist ADD COLUMN IF NOT EXISTS activated_at TIMESTAMPTZ;
ALTER TABLE waitlist ADD COLUMN IF NOT EXISTS admin_note TEXT;
ALTER TABLE lg_requests ADD COLUMN IF NOT EXISTS tokens_in INT DEFAULT 0;
ALTER TABLE lg_requests ADD COLUMN IF NOT EXISTS tokens_out INT DEFAULT 0;
ALTER TABLE lg_requests ADD COLUMN IF NOT EXISTS llm_cost_usd NUMERIC(12, 6) DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_matches_company_status ON matches(company_id, saved);
CREATE INDEX IF NOT EXISTS idx_matches_company_created ON matches(company_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_waitlist_email_lower ON waitlist (lower(email));
CREATE TABLE IF NOT EXISTS monitor_state (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'portal_html',
    adapter TEXT NOT NULL DEFAULT 'marchespublics',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    cadence_hours INT NOT NULL DEFAULT 24,
    last_run_at TIMESTAMPTZ,
    last_status TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS sectors (
    code TEXT PRIMARY KEY,
    label_fr TEXT NOT NULL,
    label_ar TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'services',
    enabled BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE IF NOT EXISTS chat_messages (
    id BIGSERIAL PRIMARY KEY,
    phone TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    intent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chat_phone ON chat_messages(phone, created_at DESC);

-- Profil entreprise étendu (tous optionnels, utilisés par le matching LLM)
ALTER TABLE companies ADD COLUMN IF NOT EXISTS budget_min NUMERIC(14, 2);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS budget_max NUMERIC(14, 2);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS certifications TEXT[] DEFAULT '{}';
ALTER TABLE companies ADD COLUMN IF NOT EXISTS qualification TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS experience_years INT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS references_projets JSONB DEFAULT '[]';
ALTER TABLE companies ADD COLUMN IF NOT EXISTS ice TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS rc TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS if_fiscal TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS website TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS linkedin TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS prefers_types TEXT[] DEFAULT '{}';
-- Typologie des opportunités (AO ouvert/restreint, bon de commande, ...)
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS opportunity_type TEXT;
-- "Nouveau" = vu pour la première fois par Soukna (stratégie sans filtre
-- de dates : la diff contre la base dit ce qui est neuf)
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMPTZ
  NOT NULL DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_opportunities_first_seen
  ON opportunities(first_seen_at DESC);
"""

# Le formulaire de la landing écrit dans waitlist via la clé publishable
# (rôle anon) : insertion seule autorisée, aucune lecture.
WAITLIST_POLICY = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'waitlist'
                   AND policyname = 'anon_insert_waitlist') THEN
        CREATE POLICY anon_insert_waitlist ON waitlist
            FOR INSERT TO anon WITH CHECK (true);
    END IF;
END $$;
"""


def init_db() -> None:
    conn = connect()
    try:
        conn.execute(SCHEMA)
        conn.execute(MIGRATIONS)
        conn.execute(WAITLIST_POLICY)
    finally:
        putconn(conn)


# -----------------------------------------------------------------------
# Entreprises (profils)
# -----------------------------------------------------------------------

def get_company_by_phone(phone: str) -> dict[str, Any] | None:
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    rows = query("SELECT * FROM companies WHERE phone = %s OR phone = %s", (phone, digits))
    return rows[0] if rows else None


def get_company(company_id: str) -> dict[str, Any] | None:
    rows = query("SELECT * FROM companies WHERE id = %s", (company_id,))
    return rows[0] if rows else None


def list_companies() -> list[dict[str, Any]]:
    return query("SELECT * FROM companies ORDER BY created_at")


def upsert_company(*, name: str, email: str | None = None, phone: str | None = None,
                   password_hash: str | None = None, sectors: list[str] | None = None,
                   keywords: list[str] | None = None, regions: list[str] | None = None,
                   size: str = "pme") -> dict[str, Any]:
    rows = query(
        """
        INSERT INTO companies (name, email, phone, password_hash, sectors, keywords, regions, size)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (email) DO UPDATE SET
            name = EXCLUDED.name, phone = COALESCE(EXCLUDED.phone, companies.phone),
            password_hash = COALESCE(EXCLUDED.password_hash, companies.password_hash),
            sectors = EXCLUDED.sectors, keywords = EXCLUDED.keywords,
            regions = EXCLUDED.regions, size = EXCLUDED.size
        RETURNING *
        """,
        (name, email, phone, password_hash, sectors or [], keywords or [], regions or [], size),
    )
    return rows[0]


def set_channel_prefs(company_id: str, whatsapp: bool, email: bool) -> None:
    execute(
        "UPDATE companies SET channel_whatsapp = %s, channel_email = %s WHERE id = %s",
        (whatsapp, email, company_id),
    )


def update_company_profile(company_id: str, *, name: str | None = None,
                           sectors: list[str] | None = None,
                           keywords: list[str] | None = None,
                           regions: list[str] | None = None,
                           size: str | None = None,
                           max_guarantee: int | None = None,
                           alert_min_score: int | None = None) -> None:
    """Mise à jour partielle du profil (seuls les champs fournis changent)."""
    sets: list[str] = []
    params: list[Any] = []
    if name is not None:
        sets.append("name = %s")
        params.append(name)
    if sectors is not None:
        sets.append("sectors = %s")
        params.append(sectors)
    if keywords is not None:
        sets.append("keywords = %s")
        params.append(keywords)
    if regions is not None:
        sets.append("regions = %s")
        params.append(regions)
    if size is not None:
        sets.append("size = %s")
        params.append(size)
    if max_guarantee is not None:
        sets.append("max_guarantee = %s")
        params.append(max_guarantee)
    if alert_min_score is not None:
        sets.append("alert_min_score = %s")
        params.append(alert_min_score)
    if not sets:
        return
    params.append(company_id)
    execute(f"UPDATE companies SET {', '.join(sets)} WHERE id = %s", tuple(params))


# -----------------------------------------------------------------------
# Opportunités / matches / digests
# -----------------------------------------------------------------------

def upsert_opportunity(**o: Any) -> bool:
    """Insère ou met à jour une opportunité (par source_ref). True si écrit."""
    rows = query(
        """
        INSERT INTO opportunities (source_ref, source, title, buyer, city, region,
                                   sector, domain_code, deadline, amount, url, raw,
                                   opportunity_type)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_ref) DO UPDATE SET
            title = EXCLUDED.title, buyer = EXCLUDED.buyer, city = EXCLUDED.city,
            region = EXCLUDED.region, sector = EXCLUDED.sector,
            domain_code = EXCLUDED.domain_code, deadline = EXCLUDED.deadline,
            amount = EXCLUDED.amount, url = EXCLUDED.url, raw = EXCLUDED.raw,
            opportunity_type = EXCLUDED.opportunity_type,
            updated_at = now()
        RETURNING (xmax = 0) AS inserted
        """,
        (o["source_ref"], o.get("source", "seed"), o["title"], o.get("buyer"),
         o.get("city"), o.get("region"), o.get("sector"), o.get("domain_code"),
         o.get("deadline"), o.get("amount"), o.get("url"),
         json.dumps(o.get("raw") or {}, ensure_ascii=False),
         o.get("opportunity_type")),
    )
    return bool(rows and rows[0]["inserted"])


def unanalyzed_opportunities(limit: int = 50) -> list[dict[str, Any]]:
    """Opportunités à venir sans match pour au moins une entreprise active."""
    return query(
        """
        SELECT o.* FROM opportunities o
        WHERE o.deadline IS NULL OR o.deadline >= CURRENT_DATE
        ORDER BY o.deadline NULLS LAST, o.created_at DESC
        LIMIT %s
        """,
        (limit,),
    )


def opportunities_without_match(company_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Opportunités à venir pas encore analysées pour cette entreprise."""
    return query(
        """
        SELECT o.* FROM opportunities o
        WHERE (o.deadline IS NULL OR o.deadline >= CURRENT_DATE)
          AND NOT EXISTS (
              SELECT 1 FROM matches m
              WHERE m.opportunity_id = o.id AND m.company_id = %s
          )
        ORDER BY o.deadline NULLS LAST, o.created_at DESC
        LIMIT %s
        """,
        (company_id, limit),
    )


def set_verdict(opportunity_id: str, company_id: str, verdict: str,
                risks: list[str]) -> None:
    execute(
        "UPDATE matches SET verdict = %s, risks = %s, updated_at = now() "
        "WHERE opportunity_id = %s AND company_id = %s",
        (verdict, json.dumps(risks, ensure_ascii=False), opportunity_id, company_id),
    )


def upsert_match(*, opportunity_id: str, company_id: str, match_score: int,
                 reasons: list[str], verdict: str, risks: list[str],
                 breakdown: dict[str, int] | None = None) -> bool:
    rows = query(
        """
        INSERT INTO matches (opportunity_id, company_id, match_score, reasons,
                             verdict, risks, breakdown)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (opportunity_id, company_id) DO UPDATE SET
            match_score = EXCLUDED.match_score, reasons = EXCLUDED.reasons,
            verdict = EXCLUDED.verdict, risks = EXCLUDED.risks,
            breakdown = EXCLUDED.breakdown, updated_at = now()
        RETURNING (xmax = 0) AS inserted
        """,
        (opportunity_id, company_id, match_score,
         json.dumps(reasons, ensure_ascii=False), verdict,
         json.dumps(risks, ensure_ascii=False),
         json.dumps(breakdown or {}, ensure_ascii=False)),
    )
    return bool(rows and rows[0]["inserted"])


def matches_for_company(company_id: str, *, min_score: int = 0, limit: int = 30,
                        opp_type: str | None = None, sector: str | None = None,
                        city: str | None = None,
                        new_since_hours: int | None = None) -> list[dict[str, Any]]:
    """Matches de l'entreprise, avec filtres optionnels :
    type d'opportunité (appel_offres/bon_commande/consultation), secteur, ville."""
    sql = """
        SELECT m.*, o.title, o.buyer, o.city, o.region, o.sector, o.deadline,
               o.amount, o.source_ref, o.url, o.source, o.opportunity_type
        FROM matches m JOIN opportunities o ON o.id = m.opportunity_id
        WHERE m.company_id = %s AND m.match_score >= %s"""
    params: list[Any] = [company_id, min_score]
    if opp_type:
        sql += " AND o.opportunity_type = %s"
        params.append(opp_type)
    if sector:
        sql += " AND (o.sector = %s OR o.sector ILIKE %s)"
        params.extend([sector, f"%{sector}%"])
    if city:
        sql += " AND o.city ILIKE %s"
        params.append(f"%{city}%")
    if new_since_hours:
        sql += " AND o.first_seen_at > now() - %s * INTERVAL '1 hour'"
        params.append(new_since_hours)
    sql += " ORDER BY m.match_score DESC, o.deadline LIMIT %s"
    params.append(limit)
    return query(sql, tuple(params))


def update_match(match_id: str, company_id: str, *, saved: bool | None = None,
                 status: str | None = None, note: str | None = None) -> dict[str, Any] | None:
    """Met à jour le dossier d'une entreprise pour UN de ses matches."""
    if saved is True and status is None:
        status = "study"  # sauvegarde par étoile => entre dans le pipeline "En étude"
    if saved is False:
        status = "new"    # retrait du dossier => retour au flux
    sets: list[str] = []
    params: list[Any] = []
    if saved is not None:
        sets.append("saved = %s")
        params.append(saved)
    if status is not None:
        sets.append("status = %s")
        params.append(status)
    if note is not None:
        sets.append("note = %s")
        params.append(note)
    if not sets:
        return get_match(match_id, company_id)
    params.extend([match_id, company_id])
    rows = query(
        f"UPDATE matches SET {', '.join(sets)}, updated_at = now() "
        "WHERE id = %s AND company_id = %s RETURNING *",
        tuple(params),
    )
    return rows[0] if rows else None


def get_match(match_id: str, company_id: str) -> dict[str, Any] | None:
    rows = query(
        """
        SELECT m.*, o.title, o.buyer, o.city, o.region, o.sector, o.deadline,
               o.amount, o.source_ref, o.url, o.source
        FROM matches m JOIN opportunities o ON o.id = m.opportunity_id
        WHERE m.id = %s AND m.company_id = %s
        """,
        (match_id, company_id),
    )
    return rows[0] if rows else None


def company_stats(company_id: str) -> dict[str, Any]:
    """KPIs du tableau de bord entreprise (une ligne par entreprise)."""
    return query(
        """
        SELECT count(*) AS total,
               count(*) FILTER (WHERE m.verdict = 'go') AS go,
               count(*) FILTER (WHERE m.verdict = 'a_etudier') AS study,
               count(*) FILTER (WHERE m.verdict = 'no_go') AS nogo,
               count(*) FILTER (WHERE m.saved) AS saved,
               count(*) FILTER (WHERE m.created_at > now() - INTERVAL '24 hours') AS new_24h
        FROM matches m WHERE m.company_id = %s
        """,
        (company_id,),
    )[0]


def notifications_for_company(company_id: str, limit: int = 10) -> list[dict[str, Any]]:
    """Notifications calculées : nouveaux matchs forts + échéances proches."""
    alert_min = (get_company(company_id) or {}).get("alert_min_score") or 70
    fresh = query(
        """
        SELECT 'match' AS kind, m.match_score AS score, o.title, o.city,
               m.created_at
        FROM matches m JOIN opportunities o ON o.id = m.opportunity_id
        WHERE m.company_id = %s AND m.verdict = 'go'
              AND m.match_score >= %s
              AND m.created_at > now() - INTERVAL '7 days'
        ORDER BY m.created_at DESC LIMIT %s
        """,
        (company_id, alert_min, limit),
    )
    deadlines = query(
        """
        SELECT 'deadline' AS kind, m.match_score AS score, o.title, o.city,
               m.updated_at AS created_at, o.deadline,
               GREATEST(0, (o.deadline - CURRENT_DATE)) AS days_left
        FROM matches m JOIN opportunities o ON o.id = m.opportunity_id
        WHERE m.company_id = %s AND m.saved
              AND o.deadline BETWEEN CURRENT_DATE AND CURRENT_DATE + 7
        ORDER BY o.deadline ASC LIMIT %s
        """,
        (company_id, limit),
    )
    items = fresh + deadlines
    items.sort(key=lambda r: r["created_at"] or "", reverse=True)
    return items[:limit]


def save_digest(*, company_id: str, content: str, channels: list[str]) -> bool:
    rows = query(
        """
        INSERT INTO digests (company_id, digest_date, content, channels)
        VALUES (%s, CURRENT_DATE, %s, %s)
        ON CONFLICT (company_id, digest_date) DO UPDATE SET
            content = EXCLUDED.content, channels = EXCLUDED.channels
        RETURNING (xmax = 0) AS inserted
        """,
        (company_id, content, json.dumps(channels, ensure_ascii=False)),
    )
    return bool(rows and rows[0]["inserted"])


def digests_for_company(company_id: str, limit: int = 14) -> list[dict[str, Any]]:
    return query(
        "SELECT digest_date, content, channels, created_at FROM digests "
        "WHERE company_id = %s ORDER BY digest_date DESC LIMIT %s",
        (company_id, limit),
    )


# -----------------------------------------------------------------------
# Observabilité (lg_*)
# -----------------------------------------------------------------------

def start_request(message_id: str, sender_phone: str) -> str:
    rows = query(
        "INSERT INTO lg_requests (message_id, sender_phone) VALUES (%s, %s) RETURNING id",
        (message_id, sender_phone),
    )
    return rows[0]["id"]


def finalize_request(request_id: str, *, route: str, outcome: str,
                     error: str | None = None,
                     llm_usage: dict[str, int] | None = None) -> None:
    usage = llm_usage or {}
    tokens_in, tokens_out = usage.get("in", 0), usage.get("out", 0)
    from . import config
    cost = (tokens_in / 1_000_000 * config.LLM_PRICE_INPUT
            + tokens_out / 1_000_000 * config.LLM_PRICE_OUTPUT)
    execute(
        """
        UPDATE lg_requests
        SET route = %s, outcome = %s, error = %s,
            tokens_in = %s, tokens_out = %s, llm_cost_usd = %s,
            finished_at = now(), latency_ms =
              GREATEST(0, (EXTRACT(EPOCH FROM (now() - started_at)) * 1000)::INT)
        WHERE id = %s
        """,
        (route, outcome, error, tokens_in, tokens_out, round(cost, 6), request_id),
    )


def log_agent(request_id: str, agent: str, duration_s: float, detail: str = "") -> None:
    execute(
        "INSERT INTO lg_logs (request_id, agent, duration_s, detail) VALUES (%s, %s, %s, %s)",
        (request_id, agent, round(duration_s, 3), detail[:500]),
    )


def mark_seen(message_id: str) -> bool:
    """True si c'est la première fois qu'on voit ce message (idempotence)."""
    rows = query(
        "INSERT INTO lg_messages_seen (message_id) VALUES (%s) "
        "ON CONFLICT (message_id) DO NOTHING RETURNING message_id",
        (message_id,),
    )
    return bool(rows)


def requests_since(hours: float = 24, limit: int = 100) -> list[dict[str, Any]]:
    return query(
        "SELECT id, message_id, sender_phone, route, outcome, error, started_at, "
        "latency_ms, tokens_in, tokens_out, llm_cost_usd "
        "FROM lg_requests WHERE started_at > now() - %s * INTERVAL '1 hour' "
        "ORDER BY started_at DESC LIMIT %s",
        (hours, limit),
    )


def logs_since(hours: float = 24, limit: int = 300) -> list[dict[str, Any]]:
    return query(
        """
        SELECT l.id, l.agent, l.duration_s, l.detail, l.created_at,
               r.message_id, r.route, r.outcome
        FROM lg_logs l JOIN lg_requests r ON r.id = l.request_id
        WHERE l.created_at > now() - %s * INTERVAL '1 hour'
        ORDER BY l.created_at DESC LIMIT %s
        """,
        (hours, limit),
    )


def start_pipeline_run() -> str:
    rows = query("INSERT INTO pipeline_runs DEFAULT VALUES RETURNING id")
    return rows[0]["id"]


# -----------------------------------------------------------------------
# Users (credentials dashboard en base) + gestion admin des entreprises
# -----------------------------------------------------------------------

def get_user_by_email(email: str) -> dict[str, Any] | None:
    rows = query("SELECT * FROM users WHERE email = %s", (email,))
    return rows[0] if rows else None


def create_user(email: str, password_hash: str, role: str = "admin") -> dict[str, Any]:
    rows = query(
        """
        INSERT INTO users (email, password_hash, role) VALUES (%s, %s, %s)
        ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash,
                                        role = EXCLUDED.role
        RETURNING *
        """,
        (email, password_hash, role),
    )
    return rows[0]


def count_users() -> int:
    return query("SELECT count(*) AS n FROM users")[0]["n"]


def update_company_admin(company_id: str, *, plan: str | None = None,
                         status: str | None = None) -> dict[str, Any] | None:
    sets: list[str] = []
    params: list[Any] = []
    if plan is not None:
        sets.append("plan = %s")
        params.append(plan)
    if status is not None:
        sets.append("status = %s")
        params.append(status)
    if not sets:
        return get_company(company_id)
    params.append(company_id)
    rows = query(
        f"UPDATE companies SET {', '.join(sets)} WHERE id = %s RETURNING *",
        tuple(params),
    )
    return rows[0] if rows else None


# -----------------------------------------------------------------------
# Observabilité agrégée (dashboard admin)
# -----------------------------------------------------------------------

def agent_stats(hours: float = 24) -> list[dict[str, Any]]:
    """Par agent : appels, moyenne, p95, max, erreurs sur la fenêtre."""
    return query(
        """
        SELECT agent, count(*) AS calls,
               ROUND(AVG(duration_s)::numeric, 3) AS avg_s,
               ROUND(percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_s)::numeric, 3) AS p95_s,
               ROUND(MAX(duration_s)::numeric, 3) AS max_s,
               count(*) FILTER (WHERE detail LIKE 'error:%%') AS errors
        FROM lg_logs
        WHERE created_at > now() - %s * INTERVAL '1 hour'
        GROUP BY agent ORDER BY calls DESC
        """,
        (hours,),
    )


def request_stats(hours: float = 24) -> dict[str, Any]:
    return query(
        """
        SELECT count(*) AS total,
               count(*) FILTER (WHERE outcome = 'ok') AS ok,
               count(*) FILTER (WHERE outcome = 'error') AS errors,
               count(*) FILTER (WHERE route = 'pipeline') AS pipeline_runs,
               ROUND(AVG(latency_ms)::numeric, 0) AS avg_latency_ms,
               ROUND(percentile_cont(0.95) WITHIN GROUP
                     (ORDER BY latency_ms)::numeric, 0) AS p95_latency_ms,
               COALESCE(SUM(tokens_in), 0) AS tokens_in,
               COALESCE(SUM(tokens_out), 0) AS tokens_out,
               ROUND(COALESCE(SUM(llm_cost_usd), 0)::numeric, 4) AS llm_cost_usd
        FROM lg_requests
        WHERE started_at > now() - %s * INTERVAL '1 hour'
        """,
        (hours,),
    )[0]


def logs_for_request(request_id: str) -> list[dict[str, Any]]:
    return query(
        "SELECT agent, duration_s, detail, created_at FROM lg_logs "
        "WHERE request_id = %s ORDER BY created_at",
        (request_id,),
    )


def get_state(key: str) -> dict[str, Any] | None:
    """État persistant clé→JSON (ex. dernier état d'alerte du monitoring)."""
    rows = query("SELECT value FROM monitor_state WHERE key = %s", (key,))
    return rows[0]["value"] if rows else None


def set_state(key: str, value: dict[str, Any]) -> None:
    execute(
        "INSERT INTO monitor_state (key, value, updated_at) VALUES (%s, %s, now()) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()",
        (key, json.dumps(value, ensure_ascii=False)),
    )


# -----------------------------------------------------------------------
# Waitlist → invitation → onboarding → essai (parcours client)
# -----------------------------------------------------------------------

def waitlist_list(*, status: str | None = None, q: str | None = None,
                  sector: str | None = None, limit: int = 300) -> list[dict[str, Any]]:
    sql = "SELECT * FROM waitlist WHERE 1=1"
    params: list[Any] = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if q:
        sql += " AND (company_name ILIKE %s OR email ILIKE %s)"
        params.extend([f"%{q}%", f"%{q}%"])
    if sector:
        sql += " AND sector = %s"
        params.append(sector)
    sql += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)
    return query(sql, tuple(params))


def waitlist_counts() -> dict[str, int]:
    rows = query(
        "SELECT status, count(*) AS n FROM waitlist GROUP BY status"
    )
    counts = {"pending": 0, "invited": 0, "active": 0, "rejected": 0}
    for r in rows:
        counts[r["status"]] = r["n"]
    return counts


# -----------------------------------------------------------------------
# Sources multiples (registre piloté depuis la console admin)
# -----------------------------------------------------------------------

def sources_list(*, enabled_only: bool = False) -> list[dict[str, Any]]:
    sql = "SELECT * FROM sources"
    if enabled_only:
        sql += " WHERE enabled = TRUE"
    return query(sql + " ORDER BY created_at")


def sources_upsert(*, name: str, base_url: str, kind: str = "portal_html",
                   adapter: str = "marchespublics", cadence_hours: int = 24,
                   enabled: bool | None = None,
                   source_id: str | None = None) -> dict[str, Any]:
    """Crée ou met à jour une source. Retourne la ligne écrite."""
    if source_id:
        rows = query(
            """UPDATE sources SET name = %s, base_url = %s, kind = %s,
               adapter = %s, cadence_hours = %s,
               enabled = COALESCE(%s, enabled) WHERE id = %s RETURNING *""",
            (name, base_url, kind, adapter, cadence_hours, enabled, source_id))
    else:
        rows = query(
            """INSERT INTO sources (name, base_url, kind, adapter, cadence_hours, enabled)
               VALUES (%s, %s, %s, %s, %s, COALESCE(%s, TRUE)) RETURNING *""",
            (name, base_url, kind, adapter, cadence_hours, enabled))
    return rows[0]


def sources_set_enabled(source_id: str, enabled: bool) -> None:
    execute("UPDATE sources SET enabled = %s WHERE id = %s", (enabled, source_id))


def sources_delete(source_id: str) -> int:
    return execute("DELETE FROM sources WHERE id = %s", (source_id,))


def sources_update_status(source_id: str, status: str) -> None:
    execute("UPDATE sources SET last_status = %s, last_run_at = now() WHERE id = %s",
            (status[:200], source_id))


# -----------------------------------------------------------------------
# Secteurs (référentiel FR/AR, seed au démarrage)
# -----------------------------------------------------------------------

def sectors_ensure(rows: list[dict[str, str]]) -> int:
    n = 0
    for r in rows:
        n += execute(
            """INSERT INTO sectors (code, label_fr, label_ar, category)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (code) DO UPDATE SET label_fr = EXCLUDED.label_fr,
               label_ar = EXCLUDED.label_ar, category = EXCLUDED.category""",
            (r["code"], r["label_fr"], r["label_ar"], r.get("category", "services")))
    return n


def sectors_list() -> list[dict[str, Any]]:
    return query("SELECT * FROM sectors WHERE enabled = TRUE ORDER BY category, label_fr")


# -----------------------------------------------------------------------
# Mémoire de conversation persistée (contexte multi-messages WhatsApp)
# -----------------------------------------------------------------------

def chat_save(phone: str, role: str, content: str, intent: str | None = None) -> None:
    execute(
        "INSERT INTO chat_messages (phone, role, content, intent) VALUES (%s, %s, %s, %s)",
        (phone or "", role, (content or "")[:2000], intent))


def chat_history(phone: str, limit: int = 8) -> list[dict[str, Any]]:
    """Derniers messages (ancien → récent) pour injecter le contexte."""
    rows = query(
        """SELECT role, content, created_at FROM chat_messages
           WHERE phone = %s ORDER BY created_at DESC LIMIT %s""",
        (phone or "", limit))
    return list(reversed(rows))


# -----------------------------------------------------------------------
# Profil entreprise étendu (champs optionnels — matching enrichi)
# -----------------------------------------------------------------------

PROFILE_EXT_FIELDS = {
    "budget_min", "budget_max", "certifications", "qualification",
    "experience_years", "references_projets", "ice", "rc", "if_fiscal",
    "website", "linkedin", "prefers_types",
}


def update_company_profile_ext(company_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    """Met à jour uniquement les champs étendus fournis (None ignorés)."""
    cols: list[str] = []
    params: list[Any] = []
    for key, value in (fields or {}).items():
        if key not in PROFILE_EXT_FIELDS or value is None:
            continue
        cols.append(f"{key} = %s")
        params.append(json.dumps(value, ensure_ascii=False)
                      if key == "references_projets" else value)
    if not cols:
        return get_company(company_id)
    params.append(company_id)
    rows = query(
        f"UPDATE companies SET {', '.join(cols)} WHERE id = %s RETURNING *",
        tuple(params))
    return rows[0] if rows else None


def waitlist_row(wid: str) -> dict[str, Any] | None:
    rows = query("SELECT * FROM waitlist WHERE id = %s", (wid,))
    return rows[0] if rows else None


def waitlist_update(wid: str, **sets: Any) -> dict[str, Any] | None:
    allowed = {"status", "invited_at", "invited_by", "activated_at", "admin_note"}
    cols: list[str] = []
    params: list[Any] = []
    for k, v in sets.items():
        if k in allowed and v is not None:
            cols.append(f"{k} = %s")
            params.append(v)
    if not cols:
        return waitlist_row(wid)
    params.append(wid)
    rows = query(
        f"UPDATE waitlist SET {', '.join(cols)} WHERE id = %s RETURNING *",
        tuple(params),
    )
    return rows[0] if rows else None


def create_invite_token(waitlist_id: str, email: str, *, days: int,
                        created_by: str) -> str:
    token = secrets.token_urlsafe(32)
    execute(
        "INSERT INTO invite_tokens (token, waitlist_id, email, expires_at, created_by) "
        "VALUES (%s, %s, %s, now() + (%s * INTERVAL '1 day'), %s)",
        (token, waitlist_id, email, days, created_by),
    )
    return token


def consume_invite_token(token: str) -> dict[str, Any] | None:
    """Retourne le jeton si valide (non utilisé, non expiré), sinon None."""
    rows = query(
        "SELECT * FROM invite_tokens WHERE token = %s AND used_at IS NULL "
        "AND expires_at > now()",
        (token,),
    )
    return rows[0] if rows else None


def mark_token_used(token: str) -> None:
    execute("UPDATE invite_tokens SET used_at = now() WHERE token = %s", (token,))


def audit(actor: str, action: str, waitlist_id: str | None = None,
          detail: str = "") -> None:
    execute(
        "INSERT INTO audit_log (actor, action, waitlist_id, detail) VALUES (%s, %s, %s, %s)",
        (actor, action, waitlist_id, detail[:500]),
    )


def email_taken(email: str, exclude_waitlist_id: str | None = None) -> bool:
    """Un compte existe déjà pour cet email (user dashboard ou entreprise).
    L'entreprise créée depuis la MÊME ligne d'attente ne compte pas comme
    conflit (elle est créée à l'invitation, avant l'onboarding)."""
    if get_user_by_email(email):
        return True
    if exclude_waitlist_id:
        rows = query(
            "SELECT 1 FROM companies WHERE lower(email) = %s "
            "AND (waitlist_id IS NULL OR waitlist_id <> %s)",
            (email, exclude_waitlist_id),
        )
    else:
        rows = query("SELECT 1 FROM companies WHERE lower(email) = %s", (email,))
    return bool(rows)


def activate_trial_company(company_id: str, *, waitlist_id: str, owner_email: str,
                           lang: str, trial_days: int = 14) -> None:
    execute(
        """
        UPDATE companies SET waitlist_id = %s, owner_email = %s, lang = %s,
               plan = 'trial', trial_started_at = now(),
               trial_ends_at = now() + (%s * INTERVAL '1 day')
        WHERE id = %s
        """,
        (waitlist_id, owner_email, lang, trial_days, company_id),
    )


def waitlist_sectors() -> list[str]:
    return [r["sector"] for r in query(
        "SELECT DISTINCT sector FROM waitlist WHERE sector IS NOT NULL ORDER BY sector"
    )]


def finish_pipeline_run(run_id: str, *, source_mode: str, ingested: int, matched: int,
                        verdicted: int, digests: int, status: str = "ok",
                        error: str | None = None) -> None:
    execute(
        """
        UPDATE pipeline_runs SET finished_at = now(), source_mode = %s, ingested = %s,
               matched = %s, verdicted = %s, digests = %s, status = %s, error = %s
        WHERE id = %s
        """,
        (source_mode, ingested, matched, verdicted, digests, status, error, run_id),
    )


def utcnow() -> datetime:
    return datetime.now(UTC)
