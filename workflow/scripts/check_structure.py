# =====================================================================
# check_structure.py — garde-fou CI : fichiers obligatoires, Agent Cards
# complètes (SemVer), docker-compose valide, .env.example cohérent.
# =====================================================================
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_FILES = [
    "README.md",
    ".env.example",
    ".gitignore",
    "docker-compose.yml",
    ".github/workflows/ci.yml",
    "docs/runbook.md",
    "docs/agent-cards/README.md",
    "docs/supabase_schema.sql",
    "workflow/requirements.txt",
    "workflow/pyproject.toml",
    "workflow/api.py",
    "workflow/soukna_graph/config.py",
    "workflow/soukna_graph/db.py",
    "workflow/soukna_graph/state.py",
    "workflow/soukna_graph/llm.py",
    "workflow/soukna_graph/prompts.py",
    "workflow/soukna_graph/graph.py",
    "workflow/soukna_graph/context.py",
    "workflow/soukna_graph/tracing.py",
    "workflow/soukna_graph/nodes/intake.py",
    "workflow/soukna_graph/nodes/orchestrator.py",
    "workflow/soukna_graph/nodes/sources.py",
    "workflow/soukna_graph/nodes/matching.py",
    "workflow/soukna_graph/nodes/verdict.py",
    "workflow/soukna_graph/nodes/digest.py",
    "workflow/soukna_graph/nodes/response.py",
    "workflow/soukna_graph/tools/portal.py",
    "workflow/soukna_graph/tools/whatsapp.py",
    "workflow/soukna_graph/tools/emailer.py",
    "workflow/soukna_graph/tools/seed_data.py",
    "workflow/tests/test_cases.json",
    "workflow/scripts/send_one.py",
    "workflow/scripts/chat_interactive.py",
    "workflow/scripts/eval_suite.py",
    "workflow/scripts/webhook_client.py",
    "workflow/scripts/cleanup_test_data.py",
    "workflow/Dockerfile",
    "dashboard/package.json",
    "dashboard/Dockerfile",
]

REQUIRED_CARD_FIELDS = ["agent", "slug", "version", "proprietaire", "equipe",
                        "objectif", "outils", "entrees", "sorties", "limites",
                        "securite"]
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")

REQUIRED_ENV_KEYS = ["DATABASE_URL", "MISTRAL_API_KEY", "KILL_SWITCH",
                     "WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID",
                     "WHATSAPP_VERIFY_TOKEN", "WHATSAPP_TEST_RECIPIENTS",
                     "SMTP_HOST", "PORTAL_ENABLED", "AUTH_SECRET",
                     "ADMIN_USERNAME", "ADMIN_PASSWORD"]


def main() -> int:
    errors: list[str] = []

    for rel in REQUIRED_FILES:
        if not (ROOT / rel).exists():
            errors.append(f"fichier manquant : {rel}")

    cards = sorted((ROOT / "docs" / "agent-cards").glob("*-agent-card.yaml"))
    if len(cards) < 5:
        errors.append(f"agent cards : {len(cards)} trouvées, 5 attendues")
    for card in cards:
        try:
            data = yaml.safe_load(card.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            errors.append(f"{card.name} : YAML invalide ({exc})")
            continue
        section = {**(data.get("carte") or {})}
        for key, value in data.items():
            if key != "carte":
                section.setdefault(key, value)
        for field in REQUIRED_CARD_FIELDS:
            if field not in section:
                errors.append(f"{card.name} : champ manquant '{field}'")
        version = str(section.get("version", ""))
        if not SEMVER.match(version):
            errors.append(f"{card.name} : version '{version}' n'est pas SemVer")

    compose_path = ROOT / "docker-compose.yml"
    try:
        compose = yaml.safe_load(compose_path.read_text(encoding="utf-8")) or {}
        services = compose.get("services") or {}
        for service in ("workflow", "dashboard"):
            if service not in services:
                errors.append(f"docker-compose : service '{service}' manquant")
    except yaml.YAMLError as exc:
        errors.append(f"docker-compose.yml : YAML invalide ({exc})")

    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    for key in REQUIRED_ENV_KEYS:
        if not re.search(rf"^{key}=", env_example, re.M):
            errors.append(f".env.example : clé manquante {key}")

    if errors:
        print("ÉCHEC de la vérification de structure :")
        for err in errors:
            print(f"  - {err}")
        return 1
    print(f"Structure OK : {len(REQUIRED_FILES)} fichiers, "
          f"{len(cards)} agent cards, compose + .env.example valides.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
