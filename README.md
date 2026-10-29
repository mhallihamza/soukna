# Soukna — Intelligence marchés publics (LangGraph + FastAPI + Next.js)

Plateforme qui repère les **appels d'offres publics marocains pertinents** pour
une entreprise, les analyse (**Match /100**, verdict indicatif GO / À ÉTUDIER /
NO-GO, risques à vérifier) et livre un **digest quotidien** par les canaux que
l'utilisateur choisit (WhatsApp, email, dashboard).

> Sources traçables · Analyse indicative · Décision humaine.

## Architecture

```
soukna/
├── workflow/            Service LangGraph + FastAPI (le « cerveau » agentique)
│   ├── soukna_graph/    Graphe 7 nœuds + observabilité (lg_*)
│   │   ├── nodes/       intake, orchestrator, sources, matching,
│   │   │                verdict, digest, response
│   │   └── tools/       portail marchespublics.gov.ma, WhatsApp, email
│   ├── api.py           Webhook + API REST (auth RBAC admin/entreprise)
│   ├── tests/           pytest hors-ligne + dataset d'évaluation
│   └── scripts/         send_one, chat_interactive, eval_suite (+ juge LLM)
├── dashboard/           Next.js : landing (FR/AR) + dashboard admin & entreprise
├── docs/
│   ├── agent-cards/     Gouvernance : 5 cartes agents (YAML, FR)
│   └── runbook.md       Détection → Diagnostic → Contention → Résolution
└── docker-compose.yml   workflow + dashboard (+ Postgres local optionnel)
```

## Démarrage rapide (Docker)

```bash
# 1. Copier la configuration
cp .env.example .env        # puis renseigner les secrets

# 2. Tout construire et lancer
docker compose up --build -d

# 3. Vérifier
curl http://localhost:8000/health      # API workflow
open http://localhost:3000             # landing + dashboard
```

## Mode développement (sans Docker)

```bash
# Terminal 1 — workflow
cd workflow
python -m venv .venv && .venv\Scripts\activate   # (Windows)
pip install -r requirements.txt
uvicorn api:app --reload --port 8000

# Terminal 2 — dashboard
cd dashboard
npm install
npm run dev
```

## Variables d'environnement

| Variable | Défaut | Rôle |
| --- | --- | --- |
| `DATABASE_URL` | postgres local | Connexion Postgres/Supabase |
| `MISTRAL_API_KEY` | *(vide)* | Clé Mistral — sans clé : mode heuristique |
| `MISTRAL_MODEL` | `codestral-latest` | Modèle d'analyse (le seul actif sur la clé fournie) |
| `WHATSAPP_TOKEN` / `WHATSAPP_PHONE_NUMBER_ID` | *(vide)* | Envoi WhatsApp Cloud API |
| `WHATSAPP_VERIFY_TOKEN` | `soukna-verify` | Vérification du webhook Meta |
| `WHATSAPP_TEST_RECIPIENTS` | *(vide)* | Liste blanche : seuls ces numéros reçoivent quand `KILL_SWITCH=true` |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` | *(vide)* | Canal email du digest |
| `KILL_SWITCH` | `true` | `true` => aucun envoi hors liste blanche |
| `PORTAL_ENABLED` | `true` | Activer le scraping du portail marchespublics.gov.ma |
| `DIGEST_HOUR` | `8` | Heure d'envoi du digest quotidien |
| `AUTH_SECRET` | `dev-secret-change-me` | Signature des tokens dashboard |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | `admin` / `admin123` | Compte admin (⚠️ changer) |

## Rôles & accès (dashboard)

| Rôle | Périmètre |
| --- | --- |
| `admin` | Tout : supervision pipeline, observabilité, sources, utilisateurs |
| `entreprise` | Son profil, ses opportunités matchées, verdicts, digest, préférences canaux |

## Endpoints de l'API (workflow)

| Méthode | Route | Rôle | Description |
| --- | --- | --- | --- |
| GET/POST | `/webhook` | public | Webhook WhatsApp Cloud API (format Meta) |
| GET | `/health` | public | Sonde de vie |
| POST | `/run` | admin | Exécute le pipeline complet (sources → matching → verdict → digest) |
| GET | `/opportunities` | entreprise | Opportunités matchées pour mon profil |
| GET/PATCH | `/profile` | entreprise | Profil entreprise + préférences canaux |
| GET | `/observability?hours=N` | admin | Requêtes + traces d'agents |
| GET | `/stats` | admin | KPIs du dashboard |

## Gouvernance (Agent Cards + runbook)

- `docs/agent-cards/README.md` — la charte (SemVer obligatoire, champs minimaux).
- `docs/agent-cards/*-agent-card.yaml` — 5 cartes : `supervisor`, `soukna-sources-agent`,
  `soukna-matching-agent`, `soukna-verdict-agent`, `soukna-digest-agent`.
- `docs/runbook.md` — Détection → Diagnostic → Contention → Résolution.

## Tests & évaluation (LLM-as-Judge)

Trois scripts exercent le **vrai webhook** (`POST /webhook`, enveloppe Meta) —
tout le pipeline s'exécute et un vrai message part vers le numéro de test :

```bash
python workflow/scripts/send_one.py "Quelles opportunités aujourd'hui ?"
python workflow/scripts/chat_interactive.py          # chat tapez-et-répondez
python workflow/scripts/eval_suite.py                # 10 cas + juge LLM
python workflow/scripts/cleanup_test_data.py         # purge des données de test
```

Dataset : `workflow/tests/test_cases.json` — chaque cas déclare `message` +
`expected` ; le juge (`MISTRAL_MODEL`) compare critère par critère et publie un
rapport dans `workflow/artifacts/` (ignoré par git).

## CI (GitHub Actions)

`.github/workflows/ci.yml` — job `structure-and-unit` (push/PR : structure,
lint ruff, tests mockés) + job `live-eval` **manuel** (10 cas réels + juge).

## Limites connues (feuille de route)

- Le portail marchespublics.gov.ma n'offre pas d'API publique documentée :
  l'agent `sources` utilise un scraper POST (postback PRADO) **best effort** —
  un changement de structure du portail peut casser l'ingestion (le runbook
  prévoit la contention : `PORTAL_ENABLED=false` + repli sur les seeds).
- Les scores/verdicts sont **indicatifs** : jamais un substitut à la lecture
  des pièces officielles du dossier.
