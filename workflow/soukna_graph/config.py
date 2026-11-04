# =====================================================================
# Configuration centrale du workflow Soukna (style 12-factor).
# Lue via .env ; aucune valeur sensible en dur dans git.
# =====================================================================
import os
from pathlib import Path

from dotenv import load_dotenv

# .env à la racine du service workflow/
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://soukna:soukna@localhost:5432/soukna")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "codestral-latest")
# Tarification LLM (USD / million de tokens) pour le coût d'observabilité.
LLM_PRICE_INPUT = float(os.getenv("LLM_PRICE_INPUT", "0.3"))
LLM_PRICE_OUTPUT = float(os.getenv("LLM_PRICE_OUTPUT", "0.9"))

# Interrupteur runtime (admin dashboard) : couper le LLM bascule tout
# le scoring sur le mode heuristique sans redémarrer le service.
LLM_ENABLED = True


def llm_ready() -> bool:
    return bool(MISTRAL_API_KEY) and LLM_ENABLED


# --- Canal WhatsApp (Cloud API Meta) ---------------------------------
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "soukna-verify")
# App Secret (Meta > WhatsApp > API > App settings) : sert à vérifier la
# signature X-Hub-Signature-256 des POST /webhook. Vide = pas de vérification
# (dev local uniquement) — à renseigner en production.
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "")

# Secret du déclencheur cron externe (cron-job.org) : header X-Cron-Secret
# sur POST /cron/run. Vide = endpoint désactivé (503). Statique, n'expire
# jamais (contrairement aux tokens admin TTL 12h).
CRON_SECRET = os.getenv("CRON_SECRET", "")
WHATSAPP_API = "https://graph.facebook.com/v21.0"

# Kill switch (runbook : phase Contention) : true => aucun envoi WhatsApp
# SAUF vers la liste blanche de test. En production (false) : tout le monde.
KILL_SWITCH = os.getenv("KILL_SWITCH", "true").strip().lower() in {"1", "true", "yes"}

_raw_test_recipients = os.getenv("WHATSAPP_TEST_RECIPIENTS", "")
TEST_RECIPIENTS = {
    "".join(ch for ch in entry.strip() if ch.isdigit())
    for entry in _raw_test_recipients.split(",")
    if entry.strip()
} - {""}


def is_test_recipient(phone: str) -> bool:
    """True si le numéro (tolérant sur +, espaces, indicatif) est whitelisté."""
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if not digits:
        return False
    if digits in TEST_RECIPIENTS:
        return True
    return any(t.endswith(digits) or digits.endswith(t) for t in TEST_RECIPIENTS)


# --- Canal email (digest) ---------------------------------------------
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "soukna@noreply.ma")
# Brevo (API HTTPS) : prioritaire en production — les hébergeurs cloud
# bloquent le SMTP sortant, jamais HTTPS. Vide = SMTP classique (local).
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
# Resend (API HTTPS, alternative à Brevo) — prioritaire si défini.
# Sans domaine vérifié, Resend n'envoie qu'à l'email du compte.
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")


def email_ready() -> bool:
    return bool(SMTP_HOST)


# --- Portail des marchés publics --------------------------------------
PORTAL_ENABLED = os.getenv("PORTAL_ENABLED", "true").strip().lower() in {"1", "true", "yes"}
PORTAL_BASE = "https://www.marchespublics.gov.ma"
PORTAL_TIMEOUT_S = int(os.getenv("PORTAL_TIMEOUT_S", "45"))
DIGEST_HOUR = int(os.getenv("DIGEST_HOUR", "8"))

# --- Référentiels (alignés sur le portail + la landing) ---------------
SECTORS = [s.strip() for s in os.getenv(
    "SECTORS",
    "Informatique, BTP, Fournitures, Services et maintenance, Conseil et études",
).split(",") if s.strip()]

REGIONS = [r.strip() for r in os.getenv(
    "REGIONS",
    "Casablanca, Rabat, Tanger, Marrakech, Agadir",
).split(",") if r.strip()]

COMPANY_SIZES = ["petite", "pme", "grande"]

# Seuils du verdict indicatif (documentés dans la carte verdict) :
VERDICT_GO_MIN = int(os.getenv("VERDICT_GO_MIN", "75"))
VERDICT_NOGO_MAX = int(os.getenv("VERDICT_NOGO_MAX", "45"))

# --- URL publique du dashboard (liens d'invitation) --------------------
APP_URL = os.getenv("APP_URL", "http://localhost:3000")

# --- Auth dashboard (rôles : admin / entreprise) ----------------------
AUTH_SECRET = os.getenv("AUTH_SECRET", "dev-secret-change-me")  # ⚠️ à changer en prod
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")        # ⚠️ à changer en prod
TOKEN_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", "12"))

# CORS : dashboard en dev (Next.js prend 3001 si 3000 est occupé)
CORS_ORIGINS = [o.strip() for o in os.getenv(
    "CORS_ORIGINS", "http://localhost:3000,http://localhost:3001,http://localhost:3002"
).split(",") if o.strip()]

# --- Agent de monitoring (seuils optionnels, défauts raisonnables) ------
MON_WINDOW_H = float(os.getenv("MON_WINDOW_H", "24"))            # fenêtre d'analyse
MON_MAX_ERROR_RATE = float(os.getenv("MON_MAX_ERROR_RATE", "20"))  # % requêtes en erreur
MON_MAX_P95_S = float(os.getenv("MON_MAX_P95_S", "120"))          # latence p95 par agent
MON_MAX_DAILY_COST_USD = float(os.getenv("MON_MAX_DAILY_COST_USD", "5"))
MON_MAX_FALLBACK_PCT = float(os.getenv("MON_MAX_FALLBACK_PCT", "50"))  # % sans LLM
MON_MAX_PORTAL_STALENESS_H = float(os.getenv("MON_MAX_PORTAL_STALENESS_H", "36"))
MON_MAX_PIPELINE_STALENESS_H = float(os.getenv("MON_MAX_PIPELINE_STALENESS_H", "30"))
MON_ALERT_COOLDOWN_H = float(os.getenv("MON_ALERT_COOLDOWN_H", "6"))   # anti-spam
MON_ALERT_EMAIL = os.getenv("MON_ALERT_EMAIL", "")   # vide = ADMIN_USERNAME
MON_ALERT_WHATSAPP = os.getenv("MON_ALERT_WHATSAPP", "")  # vide = pas d'alerte WA

# --- Base de connaissances FAQ (DataStax Astra, Data API v2) --------------
# Embedding INTÉGRÉ à Astra (service NVIDIA, champ $vectorize) : aucun
# appel externe d'embedding, ni clé Mistral/OpenAI pour vectoriser.
ASTRA_DB_API_ENDPOINT = os.getenv("ASTRA_DB_API_ENDPOINT", "")  # ex. https://<id>-us-east-2.apps.astra.datastax.com
ASTRA_DB_TOKEN = os.getenv("ASTRA_DB_TOKEN", "")               # AstraCS:... (application token)
ASTRA_DB_KEYSPACE = os.getenv("ASTRA_DB_KEYSPACE", "default_keyspace")
ASTRA_DB_COLLECTION = os.getenv("ASTRA_DB_COLLECTION", "souknabase")
FAQ_TOP_K = int(os.getenv("FAQ_TOP_K", "4"))                   # passages récupérés par question
FAQ_MAX_ANSWER_CHARS = int(os.getenv("FAQ_MAX_ANSWER_CHARS", "800"))
KB_DIR = Path(__file__).resolve().parent.parent / "kb"         # PDFs de la base de connaissances
KB_CHUNK_CHARS = int(os.getenv("KB_CHUNK_CHARS", "1200"))      # taille cible d'un passage


def astra_ready() -> bool:
    return bool(ASTRA_DB_API_ENDPOINT and ASTRA_DB_TOKEN)

