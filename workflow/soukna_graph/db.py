# =====================================================================
# Accès Postgres/Supabase : pool simple + schéma (lg_* = observabilité).
# init_db() crée les tables si absentes (utile en local) ; en Supabase,
# exécuter docs/supabase_schema.sql (équivalent) depuis le SQL editor.
# =====================================================================
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row

from . import config

_pool: psycopg.ConnectionPool | None = None


def connect() -> psycopg.Connection:
    """Connexion compatible pooler transactionnel Supabase (pgbouncer)."""
    global _pool
    if _pool is None:
        _pool = psycopg.ConnectionPool(
            config.DATABASE_URL, min_size=1, max_size=5,
            open=True, row_factory=dict_row, kwargs={"autocommit": True, "prepare_threshold": None},
        )
    return _pool.getconn()


def putconn(conn: psycopg.Connection) -> None:
    if _pool is not None:
        _pool.putconn(conn)


def query(sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
    conn = connect()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        putconn(conn)


def execute(sql: str, params: tuple | list = ()) -> int:
    conn = connect()
    try:
        cur = conn.execute(sql, params)
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
    status TEXT NOT NULL DEFAULT 'new',
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
"""


def init_db() -> None:
    conn = connect()
    try:
        conn.execute(SCHEMA)
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


def update_company_profile(company_id: str, *, sectors: list[str] | None = None,
                           keywords: list[str] | None = None,
                           regions: list[str] | None = None,
                           size: str | None = None) -> None:
    """Mise à jour partielle du profil (seuls les champs fournis changent)."""
    sets: list[str] = []
    params: list[Any] = []
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
                                   sector, domain_code, deadline, amount, url, raw)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_ref) DO UPDATE SET
            title = EXCLUDED.title, buyer = EXCLUDED.buyer, city = EXCLUDED.city,
            region = EXCLUDED.region, sector = EXCLUDED.sector,
            domain_code = EXCLUDED.domain_code, deadline = EXCLUDED.deadline,
            amount = EXCLUDED.amount, url = EXCLUDED.url, raw = EXCLUDED.raw,
            updated_at = now()
        RETURNING (xmax = 0) AS inserted
        """,
        (o["source_ref"], o.get("source", "seed"), o["title"], o.get("buyer"),
         o.get("city"), o.get("region"), o.get("sector"), o.get("domain_code"),
         o.get("deadline"), o.get("amount"), o.get("url"),
         json.dumps(o.get("raw") or {}, ensure_ascii=False)),
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
                 reasons: list[str], verdict: str, risks: list[str]) -> bool:
    rows = query(
        """
        INSERT INTO matches (opportunity_id, company_id, match_score, reasons, verdict, risks)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (opportunity_id, company_id) DO UPDATE SET
            match_score = EXCLUDED.match_score, reasons = EXCLUDED.reasons,
            verdict = EXCLUDED.verdict, risks = EXCLUDED.risks,
            status = 'new', updated_at = now()
        RETURNING (xmax = 0) AS inserted
        """,
        (opportunity_id, company_id, match_score,
         json.dumps(reasons, ensure_ascii=False), verdict,
         json.dumps(risks, ensure_ascii=False)),
    )
    return bool(rows and rows[0]["inserted"])


def matches_for_company(company_id: str, *, min_score: int = 0, limit: int = 30) -> list[dict[str, Any]]:
    return query(
        """
        SELECT m.*, o.title, o.buyer, o.city, o.region, o.sector, o.deadline,
               o.amount, o.source_ref, o.url, o.source
        FROM matches m JOIN opportunities o ON o.id = m.opportunity_id
        WHERE m.company_id = %s AND m.match_score >= %s
        ORDER BY m.match_score DESC, o.deadline
        LIMIT %s
        """,
        (company_id, min_score, limit),
    )


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
                     error: str | None = None) -> None:
    execute(
        """
        UPDATE lg_requests
        SET route = %s, outcome = %s, error = %s,
            finished_at = now(), latency_ms =
              GREATEST(0, (EXTRACT(EPOCH FROM (now() - started_at)) * 1000)::INT)
        WHERE id = %s
        """,
        (route, outcome, error, request_id),
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
        "SELECT id, message_id, sender_phone, route, outcome, error, started_at, latency_ms "
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
