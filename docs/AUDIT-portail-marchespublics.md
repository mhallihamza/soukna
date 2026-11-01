# AUDIT — Portail national marchespublics.gov.ma (2026-11-01)

Méthode : sondes HTTP réelles depuis le poste (Maroc), session PRADO complète.
Toutes les conclusions ci-dessous sont vérifiées par requêtes, pas supposées.

## 1. Corrections de perceptions antérieures

| Croyance antérieure | Réalité vérifiée |
|---|---|
| « Les critères du recherche avancée sont ignorés » | **FAUX** — le bouton `lancerRecherche` avec `keywordSearch` filtre réellement (test « gardiennage » : 10/10 résultats pertinents, 0 chevauchement avec la liste non filtrée). L'ancien test utilisait un PRADO_POSTBACK_TARGET erroné. |
| « La recherche rapide montre tout ce qu'on peut avoir » | **FAUX** — 10 résultats/recherche, mais la RECHERCHE AVANCÉE offre : mot-clé, type d'annonce, procédure, catégorie, organisme, référence, fourchette de caution, **dates de mise en ligne (début/fin)**. |
| « Pas de pagination » | **FAUX** — PagerBottom/PagerTop PRADO actifs sur les résultats : navigation page 2, 3… vérifiée (10 items/page, nouveaux refs à chaque page). Clé technique : repost avec **PRADO_PAGESTATE frais de la page de résultats** + PRADO_POSTBACK_TARGET = `ctl0$CONTENU_PAGE$resultSearch$PagerBottom$ctl2`. |

## 2. Mécaniques vérifiées

- Recherche avancée : POST `index.php?page=entreprise.EntrepriseAdvancedSearch`
  avec PRADO_PAGESTATE frais + PRADO_POSTBACK_TARGET=`ctl0$CONTENU_PAGE$AdvancedSearch$lancerRecherche`.
- Critères disponibles (champs réels du formulaire) : `keywordSearch`,
  `annonceType` (cycle de vie : information / **résultat définitif = attribué** /
  **décision de résiliation = annulé** / extrait PV / rapport achèvement),
  `procedureType` (AO ouvert=1, restreint=2, simplifié=50, AMI=37…),
  `categorie`, `orgName`, `reference`, `montantCautionMin/Max`,
  `dateMiseEnLigneCalculeStart/End`.
- Pagination : 10 items/page, postback `PagerBottom$ctl2` (suivant) avec
  pagestate frais — page 2 et 3 vérifiées sur « gardiennage ».
- Recherche rapide : 10 résultats/terme, aucun pager (limite propre au portail).

## 3. Implications pour Soukna

1. **Listage primaire possible** : recherche avancée sans critère + pagination
   = balayage complet des annonces (239 785 vues, tri par fin d'affichage) ;
   OU filtrées par `dateMiseEnLigne` (fenêtre depuis le dernier run) =
   **collecte incrémentale officielle**.
2. **Statuts officiels** : le portail publie des annonces séparées pour
   « résultat définitif » (AWARDED) et « décision de résiliation » (CANCELLED)
   → classification par type d'annonce, pas par inférence de délai.
3. Les 10 résultats/recherche de la recherche rapide restent utiles comme
   méthode secondaire (découverte par mot-clé) — les 30 termes sont conservés.
4. Comptes affichés « 0 consultations en ligne » = indicateur du menu
   (« Indicateurs clés »), sans rapport avec les résultats réels.

## 4. Plan d'implémentation (hybride, sans casser l'existant)

- `portal.py` : nouveau `advanced_search(keyword=None, annonce_type=None,
  date_start=None, date_end=None, max_pages=N) → list[dict]` (walker avec
  pagestate frais par page + normalisation via scrapers/base).
- `nodes/sources.py` : méthode PRIMAIRE = advanced_search incrémental
  (fenêtre = 7 jours glissants ou depuis le dernier run tracé) ;
  méthode SECONDAIRE = les 30 mots-clés (conservés).
- `opportunities.status` : ACTIVE/EXPIRED/CANCELLED/AWARDED/UNKNOWN
  (annonce de résultat → AWARDED, résiliation → CANCELLED, délai passé →
  EXPIRED, sinon ACTIVE) — jamais déduire annulé/attribué du seul délai.
- Logs de collecte par exécution (pages, bruts, nouveaux, doublons, statuts).
- Exploitation : fenêtre par défaut 7 jours, max_pages plafonné, délais
  1 s entre pages (politesse), aucune modification de critères interdite.

## 5. Limites vérifiées

- Le portail ne fournit pas d'API JSON publique ; tout passe par PRADO.
- 10 items/page → balayage complet 239 785 annonces ≈ 24 000 pages :
  irréaliste ET inutile ; la fenêtre de dates + types ciblés est la voie.
- ONDA/OCP : WAF avec challenge JS (403) — hors phase 1.
- Sources locales (ONEE/ONCF/Barid/Équipement) : contenu JS-rendered.
- ONSSA : WordPress mais feed = actualités, pas des marchés.
- UNGM/UNDP/Banque mondiale : API non documentées — reverse-engineering
  à mener en phase 2 (donneurs internationaux, segment PME).

## 6. Complément d'audit (même session, plus tard)

- **Pagination PRADO : FRAGILE** — le postback « suivant » avec pagestate
  frais a fonctionné (page 2/3 vérifiées, 6 nouveaux refs/page) PUIS a
  re-servi la page 1 au run suivant (0 nouveau). Comportement non
  déterministe côté portail → à retravailler avec un suivi d'état complet
  (tous les champs du formulaire, y compris boutons) avant de s'y fier.
- **Filtre dateMiseEnLigne : à confirmer** — la fenêtre 7 j renvoie bien
  10 items mais l'échantillon ressemble à la liste non filtrée ; vérifier
  en comparant deux fenêtres disjointes (semaine passée vs semaine
  courante) avant de l'utiliser en collecte incrémentale.
- La recherche rapide (10/terme) reste la SEULE méthode 100 % fiable.
  L'union de 30 termes ≈ 200 opportunités/drun, cumulatives (dédup).
- Conclusion honnête : le portail n'expose pas un balayage complet
  fiable ; la couverture « 20 000 » est un mirage (accumulation d'années,
  majoritairement expirée). Priorité qualité : fenêtre de fraîcheur +
  mots-clés larges + statuts officiels via annonceType (à exploiter).
