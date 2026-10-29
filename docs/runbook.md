# Runbook — Soukna (gestion des incidents)

Cycle en quatre phases : **Détection → Diagnostic → Contention → Résolution**.

## 1. Détection

| Signal | Où |
| --- | --- |
| `outcome = error` en rafale | Dashboard admin → Observabilité (`/observability?hours=1`) |
| `source_mode = seed` inattendu | `lg_logs` de l'agent sources (portail indisponible) |
| `whatsapp_sent: false` massif | `lg_logs` de l'agent digest |
| Healthcheck rouge | `docker compose ps` / `GET /health` |

## 2. Diagnostic

1. Identifier le `request_id` fautif dans `lg_requests` (outcome, latence).
2. Lister les traces d'agents : `SELECT agent, duration_s, detail FROM lg_logs
   WHERE request_id = :id ORDER BY id` — le premier agent en échec indique la
   couche fautive (portail, LLM, canal de livraison, base).
3. Erreurs LLM fréquentes : 429 (quota Mistral — le mode heuristique prend le
   relais), 403 (clé/modèle invalide — vérifier `MISTRAL_MODEL=codestral-latest`).

## 3. Contention (réversibles, sans déploiement)

| Symptôme | Levier (`.env` puis restart) |
| --- | --- |
| Portail cassé / structure changée | `PORTAL_ENABLED=false` → repli seeds |
| Envois indésirables suspectés | `KILL_SWITCH=true` → liste blanche uniquement |
| LLM instable | (aucun levier) le repli heuristique est automatique |
| Email en panne | vider `SMTP_HOST` → canal ignoré, dashboard reste alimenté |
| WhatsApp en panne | vider `WHATSAPP_TOKEN` → canal ignoré |

## 4. Résolution

1. Corriger (ex. adaptateur du scraper après un changement du portail).
2. Mettre à jour la carte de l'agent concerné (SemVer) **dans le même commit**.
3. Rejouer `python workflow/scripts/eval_suite.py` — 10/10 attendu.
4. Documenter l'incident en fin de runbook (date, cause, levier utilisé).

## Incidents réels (journal)

| Date | Cause | Contention | Résolution |
| --- | --- | --- | --- |
| 2026-10-29 | Portail : recherche avancée en POST postback (PRADO) dont les critères sont figés dans `PRADO_PAGESTATE` — poster des critères modifiés est ignoré (239 785 résultats non filtrés, annonces PV 2028 en tête) | — | Stratégie validée : **recherche rapide du menu gauche** (`ctl0$menuGaucheEntreprise$quickSearch` + postback `imageOk`) — 1 terme par secteur, échéances réelles. V2 possible : postback `displayDomaine` pour le filtre domaine, page de détail pour estimation/caution/qualifications. |
| 2026-10-29 | « Date limite » de la liste = parfois la **fin d'affichage** (annonces PV restées en ligne des années, ex. 20 oct 2028) | — | Sanity check dans `tools/portal.py` : échéance à plus de ~13 mois → `None` (l'échéance réelle est sur la page de détail). |
