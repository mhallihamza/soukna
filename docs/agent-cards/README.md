# Charte des Agent Cards — Soukna

Toute modification d'un agent passe par une mise à jour de sa carte **dans le
même commit** que le code.

## Règles

1. **SemVer obligatoire** : `MAJOR.MINOR.PATCH` — tout changement de
   comportement observable incrémente au minimum `MINOR`.
2. Champs minimaux : `agent`, `slug`, `version`, `proprietaire`, `equipe`,
   `plateforme`, `runtime`, `objectif`, `outils`, `entrees`, `sorties`,
   `limites`, `securite`.
3. Les `limites` documentent explicitement ce que l'agent **ne fait pas** —
   c'est le contrat de non-régression passé en revue au runbook.
4. `securite` rappelle le kill switch et la traçabilité `lg_*`.

| Agent | Slug | Rôle en une ligne |
| --- | --- | --- |
| Supervisor | `supervisor` | Intake + routage + idempotence |
| Sources | `soukna-sources-agent` | Ingestion des opportunités (portail + seeds) |
| Matching | `soukna-matching-agent` | Adéquation opportunité ↔ profil entreprise (Match /100) |
| Verdict | `soukna-verdict-agent` | Verdict indicatif GO / À ÉTUDIER / NO-GO + risques |
| Digest | `soukna-digest-agent` | Synthèse quotidienne multi-canaux (WhatsApp / email / dashboard) |

Propriétaire : **HAMZA MHALLI** · Équipe : **Aba technology**
