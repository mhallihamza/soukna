-- =====================================================================
-- Soukna — schéma Supabase complet (à exécuter dans le SQL Editor).
-- Équivalent à soukna_graph/db.py (init_db le crée aussi au démarrage
-- si le rôle postgres le permet). Idempotent : ré-exécutable sans risque.
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
    max_guarantee INT,
    alert_min_score INT NOT NULL DEFAULT 70,
    plan TEXT NOT NULL DEFAULT 'decouverte',   -- trial | decouverte | pro | business
    status TEXT NOT NULL DEFAULT 'active',     -- active | suspended
    lang TEXT DEFAULT 'fr',
    owner_email TEXT,                          -- compte client propriétaire (users.email)
    waitlist_id UUID,                          -- ligne d'attente d'origine
    trial_started_at TIMESTAMPTZ,              -- remplis à la confirmation onboarding
    trial_ends_at TIMESTAMPTZ,
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
-- breakdown : {"sector": 0-100, "keywords": ..., "region": ..., "size": ..., "history": ...}
-- status    : new (flux) | study | prep | submitted (pipeline Mes Dossiers)
CREATE TABLE IF NOT EXISTS matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opportunity_id UUID NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    match_score INT NOT NULL DEFAULT 0,
    reasons JSONB DEFAULT '[]',
    verdict TEXT,                       -- go | a_etudier | no_go
    risks JSONB DEFAULT '[]',
    breakdown JSONB DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'new',
    saved BOOLEAN NOT NULL DEFAULT FALSE,
    note TEXT,
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

-- Users dashboard (credentials en base, rôles admin ; seed au 1er démarrage)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'admin',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Waitlist de la landing (écrite par le navigateur via la clé publishable).
-- Cycle de vie : pending → invited → active (ou rejected).
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
    status TEXT NOT NULL DEFAULT 'pending',
    invited_at TIMESTAMPTZ,
    invited_by TEXT,
    activated_at TIMESTAMPTZ,
    admin_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Lien d'invitation à usage unique (le client choisit son mot de passe ;
-- aucun mot de passe n'est jamais généré, montré ou envoyé).
CREATE TABLE IF NOT EXISTS invite_tokens (
    token TEXT PRIMARY KEY,
    waitlist_id UUID NOT NULL REFERENCES waitlist(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Journal d'audit des actions admin (qui, quoi, quelle ligne, quand).
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    waitlist_id UUID,
    detail TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- Migrations idempotentes (bases créées avant l'ajout de ces colonnes)
-- ---------------------------------------------------------------------
ALTER TABLE companies ADD COLUMN IF NOT EXISTS max_guarantee INT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS alert_min_score INT NOT NULL DEFAULT 70;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS plan TEXT NOT NULL DEFAULT 'decouverte';
ALTER TABLE companies ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active';
ALTER TABLE matches ADD COLUMN IF NOT EXISTS breakdown JSONB DEFAULT '{}';
ALTER TABLE matches ADD COLUMN IF NOT EXISTS saved BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS note TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS lang TEXT DEFAULT 'fr';
ALTER TABLE companies ADD COLUMN IF NOT EXISTS owner_email TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS waitlist_id UUID;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS trial_started_at TIMESTAMPTZ;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMPTZ;
ALTER TABLE waitlist ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE waitlist ADD COLUMN IF NOT EXISTS invited_at TIMESTAMPTZ;
ALTER TABLE waitlist ADD COLUMN IF NOT EXISTS invited_by TEXT;
ALTER TABLE waitlist ADD COLUMN IF NOT EXISTS activated_at TIMESTAMPTZ;
ALTER TABLE waitlist ADD COLUMN IF NOT EXISTS admin_note TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_waitlist_email_lower ON waitlist (lower(email));

-- Index de lecture dashboard
CREATE INDEX IF NOT EXISTS idx_matches_company ON matches(company_id);
CREATE INDEX IF NOT EXISTS idx_matches_opportunity ON matches(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_matches_company_status ON matches(company_id, saved);
CREATE INDEX IF NOT EXISTS idx_matches_company_created ON matches(company_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_opportunities_deadline ON opportunities(deadline);
CREATE INDEX IF NOT EXISTS idx_lg_logs_request ON lg_logs(request_id);
CREATE INDEX IF NOT EXISTS idx_lg_requests_started ON lg_requests(started_at);

-- ---------------------------------------------------------------------
-- RLS : le service n'accède à la base QUE via DATABASE_URL (rôle
-- postgres/service), jamais depuis le navigateur. On verrouille donc
-- tout par défaut ; aucun client anon/authentifié ne lit ces tables.
-- ---------------------------------------------------------------------
ALTER TABLE companies        ENABLE ROW LEVEL SECURITY;
ALTER TABLE opportunities    ENABLE ROW LEVEL SECURITY;
ALTER TABLE matches          ENABLE ROW LEVEL SECURITY;
ALTER TABLE digests          ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_runs    ENABLE ROW LEVEL SECURITY;
ALTER TABLE lg_requests      ENABLE ROW LEVEL SECURITY;
ALTER TABLE lg_logs          ENABLE ROW LEVEL SECURITY;
ALTER TABLE lg_messages_seen ENABLE ROW LEVEL SECURITY;
ALTER TABLE users            ENABLE ROW LEVEL SECURITY;
ALTER TABLE waitlist         ENABLE ROW LEVEL SECURITY;
ALTER TABLE invite_tokens    ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log        ENABLE ROW LEVEL SECURITY;

-- Exception : la landing insère dans waitlist avec la clé publishable
-- (rôle anon). Insertion seule, aucune lecture ni modification possible.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'waitlist'
                   AND policyname = 'anon_insert_waitlist') THEN
        CREATE POLICY anon_insert_waitlist ON waitlist
            FOR INSERT TO anon WITH CHECK (true);
    END IF;
END $$;
