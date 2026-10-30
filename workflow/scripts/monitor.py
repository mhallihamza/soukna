# =====================================================================
# monitor.py — agent de monitoring : exécute les checks, affiche le
# rapport, persiste l'état et envoie les alertes (email/WhatsApp) si
# dégradation nouvelle ou cooldown écoulé.
#
# Planification (comme le digest) :
#   Windows (schtasks)  : toutes les heures
#     schtasks /Create /TN "SouknaMonitoring" /SC HOURLY /F /TR ^
#       "cmd /c cd /d C:\Users\PC\Desktop\soukna\workflow && py scripts\monitor.py"
#   Linux (cron) : 0 * * * * cd /srv/soukna/workflow && python scripts/monitor.py
#
# Code retour : 0 = sain, 1 = avertissements, 2 = critique
# (pratique standard pour la supervision externe).
# =====================================================================
from __future__ import annotations

import argparse
import json
import sys

sys.path.insert(0, ".")

from soukna_graph import monitoring  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Agent de monitoring Soukna — rapport + alertes")
    parser.add_argument("--no-alert", action="store_true",
                        help="afficher le rapport sans envoyer d'alertes")
    args = parser.parse_args()

    report = monitoring.run_checks()
    alerts = {} if args.no_alert else monitoring.maybe_alert(report)

    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    if alerts.get("sent"):
        print(f"alertes envoyées : {', '.join(alerts['sent'])}", file=sys.stderr)
    elif alerts.get("reason"):
        print(f"alertes : {alerts['reason']}", file=sys.stderr)

    return {"ok": 0, "warn": 1, "crit": 2}.get(report.get("status", "ok"), 0)


if __name__ == "__main__":
    sys.exit(main())
