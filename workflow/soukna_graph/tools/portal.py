# =====================================================================
# Scraper du portail marchespublics.gov.ma (carte soukna-sources-agent).
#
# Stratégie VALIDÉE EN LIVE (2026-10-29) :
#   • La recherche avancée est un postback PRADO dont les critères
#     (dates, catégories, domaines) sont figés dans PRADO_PAGESTATE :
#     poster des critères modifiés est ignoré (239 785 résultats non
#     filtrés, triés par fin d'affichage → annonces PV 2028 en tête).
#   • EN REVANCHE, la **recherche rapide** du menu gauche
#     (`ctl0$menuGaucheEntreprise$quickSearch` + postback
#     `ctl0$menuGaucheEntreprise$imageOk`) fonctionne parfaitement :
#     résultats pertinents, échéances réelles, lieux d'exécution.
#   → On lance une recherche rapide par secteur Soukna (1 terme
#     représentatif), on agrège, déduplique, trie par échéance
#     croissante. Un terme en échec n'empêche pas les autres ; si tout
#     échoue, l'exception remonte et le nœud sources replie sur les
#     seeds (runbook : PORTAL_ENABLED=false pour contention).
# =====================================================================
from __future__ import annotations

import re
import time
from datetime import date
from typing import Any
from unicodedata import normalize

import requests

from .. import config

BASE = config.PORTAL_BASE
SEARCH_PAGE = f"{BASE}/index.php"
SEARCH_PARAMS = {"page": "entreprise.EntrepriseAdvancedSearch", "AllCons": None,
                 "EnCours": None, "searchAnnCons": None}
QUICK_SEARCH_FIELD = "ctl0$menuGaucheEntreprise$quickSearch"
QUICK_SEARCH_BUTTON = "ctl0$menuGaucheEntreprise$imageOk"
UA = {"User-Agent": "Mozilla/5.0 (compatible; SouknaBot/1.0; +https://soukna.ma)"}

# Couverture ÉTENDUE : un terme de recherche rapide par secteur du
# référentiel (18) + un terme dédié aux bons de commande (cible PME/TPE).
# Validé live pour les 5 premiers (informatique=232, travaux=2310,
# fourniture=437, maintenance=250, étude=506). Un terme en échec
# n'empêche pas les autres (résilience par terme).
# 30 termes : le portail ne renvoie que les 10 plus proches échéances
# PAR recherche — chaque terme supplémentaire élargit l'union couverte
# (synonymes métier par secteur + termes ciblés TPE/PME).
SEARCH_TERMS: dict[str, str] = {
    # Informatique & numérique
    "Informatique": "informatique",
    "Numérique": "numérique",
    "Logiciel": "logiciel",
    "Cybersécurité": "cybersécurité",
    # Travaux & BTP
    "Travaux & BTP": "travaux",
    "Construction": "construction",
    "Réhabilitation": "réhabilitation",
    # Fournitures
    "Fournitures": "fourniture",
    "Mobilier": "mobilier",
    "Équipements": "équipement",
    # Services techniques
    "Maintenance": "maintenance",
    "Énergie": "électricité",
    "Eau & assainissement": "assainissement",
    "Télécoms": "télécom",
    # Services support (cœur PME/TPE)
    "Nettoyage": "nettoyage",
    "Gardiennage": "gardiennage",
    "Transport": "transport",
    "Impression": "imprimerie",
    "Formation": "formation",
    "Études & conseil": "étude",
    "Audit": "audit",
    "Architecture": "architecture",
    "Traduction": "traduction",
    "Photographie": "photographie",
    "Catering & traiteur": "traiteur",
    "Agroalimentaire": "alimentaire",
    "Santé & médical": "médical",
    "Environnement": "déchets",
    "Communication": "communication",
    # Cible TPE/PME : les bons de commande (petits montants, procédure simple)
    "Bons de commande": "bons de commande",
}

MONTHS_FR = {
    "janv": 1, "fevr": 2, "févr": 2, "mars": 3, "avr": 4, "mai": 5, "juin": 6,
    "juil": 7, "aout": 8, "août": 8, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
    "déc": 12,
}


# Correspondance objet → secteur (terme de recherche = secteur principal ;
# cette déduction reste disponible comme repli et pour les tests).
SECTOR_KEYWORDS: list[tuple[str, list[str]]] = [
    ("Informatique", ["informatique", "numérique", "numerique", "logiciel",
                      "plateforme", "digital", "système d'information",
                      "télécom", "telecom", "hébergement", "application",
                      "cybersécurité", "cybersecurite", "web", "digitalisation"]),
    ("BTP", ["construction", "travaux", "réhabilitation", "bâtiment", "batiment",
             "génie civil", "voirie", "aménagement", "amenagement", "route",
             "maçonnerie", "terrassement", "parking"]),
    ("Fournitures", ["fourniture", "acquisition", "équipement", "mobilier",
                     "matériel", "materiel", "consommables"]),
    ("Services et maintenance", ["maintenance", "nettoyage", "gardiennage",
                                 "entretien", "propreté", "sécurité privée",
                                 "reprographie", "transport",
                                 "location de véhicules"]),
    ("Conseil et études", ["étude", "etude", "conseil", "audit", "assistance",
                           "ingénierie", "ingenierie", "formation", "conception",
                           "programmation", "expertise"]),
]


def _sector_from_title(title: str) -> str:
    low = title.lower()
    best, best_hits = "", 0
    for sector, words in SECTOR_KEYWORDS:
        hits = sum(1 for w in words if re.search(rf"\b{re.escape(w)}", low))
        if hits > best_hits:
            best, best_hits = sector, hits
    return best


def _parse_form(html: str) -> dict[str, str]:
    """Champs hidden + text du formulaire principal (ordre d'attributs libre)."""
    fields: dict[str, str] = {}
    form_m = re.search(r'<form[^>]*id="ctl0_ctl2"[^>]*>(.*?)</form>', html, re.S)
    scope = form_m.group(1) if form_m else html
    for m in re.finditer(r"<input\b[^>]*>", scope):
        tag = m.group(0)
        name_m = re.search(r'name="([^"]+)"', tag)
        if not name_m:
            continue
        type_m = re.search(r'type="([^"]+)"', tag)
        itype = (type_m.group(1).lower() if type_m else "text")
        if itype not in {"hidden", "text"}:
            continue
        value_m = re.search(r'value="([^"]*)"', tag)
        fields[name_m.group(1)] = value_m.group(1) if value_m else ""
    return fields


def _strip_tags(block: str) -> list[str]:
    text = re.sub(r"<script.*?</script>", " ", block, flags=re.S)
    text = re.sub(r"<[^>]+>", "\n", text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return [line for line in lines if line]


def _after_label(lines: list[str], label: str, stops: tuple[str, ...]) -> str:
    """Texte qui suit un libellé (« Objet : », « Acheteur public : »…).

    Le portail découpe les libellés sur deux lignes (« Objet » puis «: »)
    ou les écrit sur une seule — les deux formes sont gérées.
    """
    residues = {":", "...", "…", "•"}
    for i, line in enumerate(lines):
        m = re.match(label + r"\s*:?\s*(.*)$", line, re.I)
        if m:
            same_line = m.group(1).strip()
            j = i + 1
            while j < len(lines) and lines[j] in residues:
                j += 1
            out: list[str] = []
            if same_line and same_line not in residues:
                out.append(same_line)
            for nxt in lines[j:]:
                if not nxt or nxt in residues or any(nxt.startswith(s) for s in stops):
                    break
                out.append(nxt)
            return " ".join(out).strip()
    return ""


def _parse_deadline(text: str) -> str | None:
    m = re.search(r"(\d{1,2})\s+([A-Za-zÀ-ÿ]{3,5})\.?\s+(\d{4})", text)
    if not m:
        return None
    month_key = normalize("NFKD", m.group(2).lower()).encode("ascii", "ignore").decode()[:4]
    month = MONTHS_FR.get(month_key)
    if not month:
        return None
    try:
        return date(int(m.group(3)), month, int(m.group(1))).isoformat()
    except ValueError:
        return None


def _parse_rows(html: str) -> list[dict[str, Any]]:
    """Un bloc de résultat par index N (`...tableauResultSearch_ctlN_...`)."""
    items: list[dict[str, Any]] = []
    for n in range(60):
        marker = f'id="ctl0_CONTENU_PAGE_resultSearch_tableauResultSearch_ctl{n}_'
        start = html.find(marker)
        if start == -1:
            break
        next_marker = f'id="ctl0_CONTENU_PAGE_resultSearch_tableauResultSearch_ctl{n + 1}_'
        end = html.find(next_marker, start)
        if end != -1:
            # Reculer au début du tag contenant le marqueur suivant : sinon
            # un fragment de balise coupée (« <div ») se glisse dans les valeurs.
            tag_start = html.rfind("<", start, end)
            if tag_start != -1:
                end = tag_start
        block = html[start:end if end != -1 else start + 25000]
        lines = _strip_tags(block)

        ref_m = re.search(
            rf'id="ctl0_CONTENU_PAGE_resultSearch_tableauResultSearch_ctl{n}_referencem"[^>]*>([^<]+)<',
            block,
        )
        link_m = re.search(r'href="([^"]*EntrepriseDetailsConsultation[^"]*)"', block)
        title = _after_label(lines, r"Objet\b", ("Détail", "Estimation", "Acheteur", "Date"))
        buyer = _after_label(lines, r"Acheteur public\b", ("Estimation", "Date", "Lieu"))
        place = _after_label(lines, r"Lieu d.exécution\b", ("AOO", "AOJR", "Référence", "Détail"))
        amount = _after_label(lines, r"Estimation TTC[^:]*", ("Acheteur", "Date", "Lieu"))
        deadline = _parse_deadline(block)

        ref = (ref_m.group(1).strip() if ref_m else "")
        if not ref and link_m:
            idm = re.search(r"refConsultation=(\d+)", link_m.group(1))
            ref = f"ref{idm.group(1)}" if idm else f"blk{n}"
        source_ref = f"portal:{ref}"

        city = place.title() if place else ""
        # Le portail affiche la « date de fin d'affichage » (annonces PV
        # restées en ligne des années) : au-delà de ~13 mois, date non
        # fiable → None (l'échéance réelle est sur la page de détail, v2).
        if deadline:
            try:
                dl_date = date.fromisoformat(deadline)
                if (dl_date - date.today()).days > 400:
                    deadline = None
            except ValueError:
                deadline = None
        href = link_m.group(1) if link_m else ""
        url = href if href.startswith("http") else (BASE + href if href else "")
        items.append({
            "source_ref": source_ref,
            "title": title[:250] or f"Consultation {ref}",
            "buyer": buyer[:180],
            "city": city,
            "region": city,
            "sector": "",
            "domain_code": "",
            "deadline": deadline,
            "amount": amount[:80],
            "url": url,
            "raw": {"ref": ref},
        })
    return items


def _quick_search(term: str) -> list[dict[str, Any]]:
    """Recherche rapide du menu gauche : GET (état) → POST (postback)."""
    with requests.Session() as session:
        session.headers.update(UA)
        r0 = session.get(SEARCH_PAGE, params=SEARCH_PARAMS,
                         timeout=config.PORTAL_TIMEOUT_S)
        r0.raise_for_status()
        fields = _parse_form(r0.text)
        if "PRADO_PAGESTATE" not in fields:
            raise RuntimeError("portail : PRADO_PAGESTATE introuvable (structure changée ?)")

        fields[QUICK_SEARCH_FIELD] = term
        fields[QUICK_SEARCH_BUTTON] = "OK"
        fields["PRADO_POSTBACK_TARGET"] = QUICK_SEARCH_BUTTON

        r1 = session.post(SEARCH_PAGE, params=SEARCH_PARAMS, data=fields,
                          timeout=config.PORTAL_TIMEOUT_S)
        r1.raise_for_status()
        return _parse_rows(r1.text)




def advanced_search(keyword: str | None = None, annonce_type: str | None = None,
                    date_start: str | None = None, date_end: str | None = None,
                    max_pages: int = 40, max_repeats: int = 3,
                    progress_cb: Any = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """progress_cb(page:int, collected:int, new:int) — suivi live du walk."""
    """Recherche avancée OFFICIELLE avec pagination robuste.

    Retourne (items_uniques, stats). La pagination PRADO est parfois
    non déterministe (page 1 re-servie) : chaque page répétée est
    recomptée et re-tentée (jamais acceptée en silence) ; après
    max_repeats répétitions, la marche s'arrête honnêtement.

    pagestate_provider : callback optionnel (html, fields) -> fields pour
    persister/récupérer l'état entre runs (réservé phase 3).
    """
    import time as _time

    s = requests.Session()
    s.headers.update(UA)
    stats: dict[str, Any] = {
        "pages": 0, "pages_repeated": 0, "retries": 0, "re_searches": 0,
        "raw_items": 0, "empty_pages": 0, "last_page_items": 0,
    }
    r0 = s.get(SEARCH_PAGE, params=SEARCH_PARAMS, timeout=config.PORTAL_TIMEOUT_S)
    fields = _parse_form(r0.text)
    if keyword:
        fields["ctl0$CONTENU_PAGE$AdvancedSearch$keywordSearch"] = keyword
    if annonce_type:
        fields["ctl0$CONTENU_PAGE$AdvancedSearch$annonceType"] = str(annonce_type)
    if date_start:
        fields["ctl0$CONTENU_PAGE$AdvancedSearch$dateMiseEnLigneCalculeStart"] = date_start
    if date_end:
        fields["ctl0$CONTENU_PAGE$AdvancedSearch$dateMiseEnLigneCalculeEnd"] = date_end
    submit = "ctl0$CONTENU_PAGE$AdvancedSearch$lancerRecherche"
    fields[submit] = "Lancer la recherche"
    fields["PRADO_POSTBACK_TARGET"] = submit

    collected: dict[str, dict[str, Any]] = {}
    repeats = 0
    while stats["pages"] < max_pages:
        r = s.post(SEARCH_PAGE, params=SEARCH_PARAMS, data=fields,
                   timeout=config.PORTAL_TIMEOUT_S)
        html = r.text
        stats["pages"] += 1
        items = _parse_rows(html)
        stats["raw_items"] += len(items)
        stats["last_page_items"] = len(items)
        if not items:
            stats["empty_pages"] += 1
            break
        new = [i for i in items if str(i.get("source_ref")) not in collected]
        for it in items:
            collected[str(it.get("source_ref"))] = it
        if progress_cb:
            progress_cb(stats["pages"], len(collected), len(new))
        if new:
            repeats = 0                     # progression saine
        else:
            repeats += 1
            stats["pages_repeated"] += 1
            if repeats >= max_repeats:
                break                       # arrêt honnête, pas de silence
            stats["retries"] += 1
            _time.sleep(2.0)                # re-tenter la même cible
            continue
        m = re.search(
            r'id="ctl0_CONTENU_PAGE_resultSearch_PagerBottom_(ctl\d+)"'
            r'[^>]*>\s*<img[^>]*fleche-suivant', html)
        if not m:
            break                           # dernière page : pager suivant inactif
        fields = _parse_form(html)          # PAGESTATE frais de CETTE page
        # ATTENTION : CONTENU_PAGE contient un underscore littéral — ne
        # JAMAIS remplacer tous les « _ » par « $ » (target invalide => le
        # portail ré-serve la page 1 en silence, bug racine de la phase 1).
        fields["PRADO_POSTBACK_TARGET"] = (
            f"ctl0$CONTENU_PAGE$resultSearch$PagerBottom${m.group(1)}")
        # PRADO exige le paramètre de commande ET la RE-CRITÈRE : la page
        # de résultats ne ré-echo pas keywordSearch — sans la re-forcer,
        # le pager ré-exécute la recherche SANS filtre et ré-serve la
        # même page (cause racine trouvée le 2026-11-01 : 44 uniques
        # pour « gardiennage » avec le critère re-forcé, contre 9-10 sans).
        if keyword:
            fields["ctl0$CONTENU_PAGE$AdvancedSearch$keywordSearch"] = keyword
        if annonce_type:
            fields["ctl0$CONTENU_PAGE$AdvancedSearch$annonceType"] = str(annonce_type)
        if date_start:
            fields["ctl0$CONTENU_PAGE$AdvancedSearch$dateMiseEnLigneCalculeStart"] = date_start
        if date_end:
            fields["ctl0$CONTENU_PAGE$AdvancedSearch$dateMiseEnLigneCalculeEnd"] = date_end
        fields["PRADO_POSTBACK_PARAMETER"] = "next"
        _time.sleep(1.0)                    # politesse portail
    return list(collected.values()), stats

def fetch_consultations(max_items: int = 200, per_term: int = 10) -> list[dict[str, Any]]:
    """Agrège les consultations par secteur (1 recherche rapide chacun).

    La page de résultats contient jusqu'à ~60 lignes : lire 15 par terme
    ne coûte RIEN de plus (même page téléchargée). Résilient : un terme
    en échec n'empêche pas les autres ; une exception n'est levée que si
    AUCUN terme n'aboutit (repli seeds appelant).
    """
    collected: dict[str, dict[str, Any]] = {}
    for sector, term in SEARCH_TERMS.items():
        try:
            items = _quick_search(term)
        except (requests.RequestException, RuntimeError):
            continue
        for item in items[:per_term]:
            item["sector"] = sector
            item["source"] = "portal"
            collected.setdefault(str(item["source_ref"]), item)
        time.sleep(1.0)  # politesse envers le portail
    if not collected:
        raise RuntimeError("portail : aucun résultat sur tous les termes de recherche")
    ranked = sorted(
        collected.values(),
        key=lambda x: (x.get("deadline") is None, x.get("deadline") or ""),
    )
    return ranked[:max_items]
