-- =====================================================================
-- Soukna — schéma Supabase (à exécuter dans le SQL Editor du projet).
-- Équivalent à soukna_graph/db.py:SCHEMA (init_db le crée aussi au
-- démarrage si le rôle postgres le permet).
-- =====================================================================

create extension if not exists pgcrypto;

-- Entreprises (profils + préférences de canaux, opt-in strict)
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

-- Opportunités (source_ref unique : référence portail ou seed)
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

-- Matches (uniques par opportunité × entreprise)
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

-- Digests (un par entreprise et par jour)
CREATE TABLE IF NOT EXISTS digests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    digest_date DATE NOT NULL,
    content TEXT NOT NULL,
    channels JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, digest_date)
);

-- Exécutions du pipeline (admin /run + cron)
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

-- Observabilité (même contrat que le projet clinique)
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

-- Index de lecture dashboard
CREATE INDEX IF NOT EXISTS idx_matches_company ON matches(company_id);
CREATE INDEX IF NOT EXISTS idx_matches_opportunity ON matches(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_opportunities_deadline ON opportunities(deadline);
CREATE INDEX IF NOT EXISTS idx_lg_logs_request ON lg_logs(request_id);
CREATE INDEX IF NOT EXISTS idx_lg_requests_started ON lg_requests(started_at);
