# =====================================================================
# Parser du portail : fixture HTML hors-ligne reproduisant la structure
# réelle observée en live (blocs ctlN, libellés sur 1 ou 2 lignes).
# =====================================================================
from soukna_graph.tools.portal import _after_label, _parse_deadline, _parse_rows, _sector_from_title

FIXTURE = """
<div>en-tête page</div>
<div id="ctl0_CONTENU_PAGE_resultSearch_tableauResultSearch_ctl0_referencem">13/2026/ANEP</div>
<span id="ctl0_CONTENU_PAGE_resultSearch_tableauResultSearch_ctl0_infosObjet">
Objet
:
La réalisation d'un cycle de formation sur les lots architecturaux
</span>
<a href="https://www.marchespublics.gov.ma/?page=entreprise.EntrepriseDetailsConsultation&refConsultation=1052197&orgAcronyme=o8p">Détail</a>
<span>Estimation TTC (en DH) :</span>
<span>Acheteur public
:
AGENCE NATIONALE DES EQUIPEMENTS PUBLICS</span>
<span>Date limite de remise des plis</span>
<span>Ven 20 Nov 2026</span>
<span>20:45</span>
<span>Lieu d'exécution</span>
<span>RABAT</span>
<div id="ctl0_CONTENU_PAGE_resultSearch_tableauResultSearch_ctl1_referencem">14/2026/ANEP</div>
<span id="ctl0_CONTENU_PAGE_resultSearch_tableauResultSearch_ctl1_infosObjet">Objet : Maintenance et évolution d'une plateforme de gestion</span>
<a href="https://www.marchespublics.gov.ma/?page=entreprise.EntrepriseDetailsConsultation&refConsultation=1052100&orgAcronyme=o8p">Détail</a>
<span>Acheteur public : AGENCE TEST</span>
<span>Date limite de remise des plis</span>
<span>Lun 01 Déc 2026</span>
<span>Lieu d'exécution</span>
<span>CASABLANCA</span>
"""


def test_parse_rows_extracts_two_blocks():
    items = _parse_rows(FIXTURE)
    assert len(items) == 2


def test_block_fields():
    items = _parse_rows(FIXTURE)
    first = items[0]
    assert first["source_ref"] == "portal:13/2026/ANEP"
    assert "cycle de formation" in first["title"]
    assert "EQUIPEMENTS PUBLICS" in first["buyer"]
    assert first["deadline"] == "2026-11-20"
    assert first["city"] == "Rabat"
    assert "refConsultation=1052197" in first["url"]


def test_one_line_labels_also_parsed():
    items = _parse_rows(FIXTURE)
    second = items[1]
    assert "plateforme de gestion" in second["title"]
    assert second["buyer"] == "AGENCE TEST"
    assert second["deadline"] == "2026-12-01"
    assert second["city"] == "Casablanca"


def test_sector_inferred_from_title():
    assert _sector_from_title("Maintenance et évolution d'une plateforme de gestion") == "Informatique"
    assert _sector_from_title("Travaux d'aménagement de deux parkings") == "BTP"
    assert _sector_from_title("Fourniture de mobilier de bureau") == "Fournitures"
    assert _sector_from_title("Prestations de nettoyage des locaux") == "Services et maintenance"
    assert _sector_from_title("Étude de protection contre les inondations") == "Conseil et études"


def test_sector_not_derived_from_buyer_name_in_title():
    # « ...la SDR Casablanca-Settat Développement » ne doit PAS donner Informatique
    assert _sector_from_title("Prestations de nettoyage des locaux de la SDR Casablanca-Settat Développement") \
        == "Services et maintenance"


def test_parse_deadline_french_months():
    assert _parse_deadline("Ven 20 Nov 2026") == "2026-11-20"
    assert _parse_deadline("Lun 01 Déc 2026") == "2026-12-01"
    assert _parse_deadline("Mer 15 Janv 2027") == "2027-01-15"
    assert _parse_deadline("pas de date ici") is None


def test_after_label_skips_residues():
    lines = ["Acheteur public", ":", "AGENCE TEST", "Date limite"]
    assert _after_label(lines, r"Acheteur public\b", ("Date",)) == "AGENCE TEST"


def test_far_future_deadline_is_neutralized():
    # Une échéance à 2028 (fin d'affichage PV) doit devenir None
    html = FIXTURE.replace("Ven 20 Nov 2026", "Ven 20 Oct 2028")
    items = _parse_rows(html)
    assert items[0]["deadline"] is None
