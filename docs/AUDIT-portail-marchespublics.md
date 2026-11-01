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

## 7. PHASE 1 — Résultat du fix pagination (2026-11-01 soir)

**Cause racine trouvée** : le postback du pager PRADO exige
`PRADO_POSTBACK_PARAMETER = "next"` (paramètre de commande). Sans lui →
la page 1 est re-servie (preuve : variant ctl2+param → 6 nouveaux refs
contre 0 sans param, même session).

**Mais** : le comportement reste NON DÉTERMINISTE entre sessions
(re-test du walker complet → 3 pages répétées, 9 uniques). Hypothèse
principale : load-balancer sans sessions collantes — l'état PRADO vit
sur un back-end, le postback suivant retombe sur un autre.

**État du code** : `advanced_search()` robuste (comptage des répétitions,
2 re-tentatives, arrêt honnête, stats complètes) + le paramètre de
commande. À poursuivre : re-recherche de ré-établissement entre
répétitions + test multi-sessions ; puis phases 2-5.

## 8. CAUSE RACINE DÉFINITIVE TROUVÉE (pagination 100 % fiable)

Le `.replace("_", "$")` sur l'ID du bouton pager corrompait
`CONTENU_PAGE` → `CONTENU$PAGE` (l'underscore est LITTÉRAL dans le nom
de la zone). Cible invalide → le portail ré-servait la page 1 en
silence. Tout le « caractère aléatoire » observé venait de là.

**Fix** : extraire uniquement le suffixe `ctlN` du bouton détecté et
reconstruire `ctl0$CONTENU_PAGE$resultSearch$PagerBottom$ctlN`.

**PREUVES (gardiennage, max_pages=12)** : pages=12, répétées=0,
bruts=120, uniques=84, durée 74 s. La pagination est fiable.

## 9. Audit des sections (annonceType / categorie) — en cours

- `annonceType` : 0=tous · 2=information (programmes prévisionnels) ·
  **4=résultat définitif (AWARDED)** · 5=extrait PV · 6=rapport achèvement ·
  **8=décision de résiliation (CANCELLED)** · 9=rapport présentation.
- `procedureType` : 20 procédures (AO ouvert=1, restreint=2, simplifié=50…).
- `categorie` : 1=Travaux · 2=Fournitures · 3=Services — **pas de BC
  dédié** : les bons de commande passent par procedureType/categorie à
  identifier encore (ou listés comme consultations ordinaires).
- Walker paginé validé sur annonceType=4 (20 items/2 pages) MAIS les
  titres ressemblent aux AO ordinaires → **vérifier l'application réelle
  du filtre** en comparant les refs avec la liste non filtrée avant de
  classifier en AWARDED. Étape suivante immédiate.
- Ne PAS marquer AWARDED/CANCELLED sans preuve de filtrage effectif.

## 10. Phase 1 (redesign sans mots-clés) — capacités vérifiées live

| Capacité testée | Verdict (preuves) |
|---|---|
| Recherche avancée AVEC mot-clé + pagination | ✅ fiable (12 pages, 84 uniques gardiennage, 0 répétition) |
| Fenêtres de dates SANS mot-clé | ❌ **NON appliquées** : deux fenêtres disjointes (20-26/10 vs 13-19/10) renvoient les MÊMES 5 items. `dateMiseEnLigneCalcule*` = champs « calculés » (probablement lecture seule / panneau masqué). |
| Sections annonceType (2/4/5/6/8/9) | ⚠️ accessibles + pagination OK (20 items/2 pages sur type=4) — **application du filtre à vérifier** par comparaison de refs avant classification. |
| categorie | Travaux(1)/Fournitures(2)/Services(3) — **pas de BC dédié**. |
| Bons de commande | Section non localisée (1 740 observés par l'utilisateur) — à retrouver (nav du portail / autre route). |
| Balayage non filtré | 239 785 annonces, tri par fin d'affichage (PV lointaines d'abord) — marche bornée possible mais tri défavorable. |

## 11. Architecture retenue (proposée)

- **PRIMAIRE (sans mots-clés)** : collecteurs par section `annonceType`
  (information, résultats, PV, achèvement, résiliation) avec pagination
  fiable → couverture du cycle de vie complet. Vérifier l'application
  effective de chaque filtre (comparaison de refs) avant classification.
- **Consultations en cours** : marche bornée de la liste non filtrée
  (fenêtre de pages) — le tri du portail est défavorable mais couvre.
- **SECONDAIRE (conservé)** : les 30 mots-clés quick search (découverte).
- **Datation incrémentale** : bloquée tant que le filtre de dates n'est
  pas craqué (piste : panneau « plus de critères » masqué à explorer via
  postback du toggle, ou sélecteur de période réel à localiser).
- **BC** : localiser la section réelle (1 740 observés) avant collecteur.
- **Statuts** : ACTIVE (vivant) / EXPIRED (délai passé, preuve = date) /
  AWARDED (vu dans annonceType=4) / CANCELLED (vu dans annonceType=8) /
  UNKNOWN — jamais par inférence du seul délai.
- Matching par entreprise APRÈS collecte centrale (une base commune).
