# =====================================================================
# Orchestrateur : classification heuristique (repli sans LLM).
# Leçons du projet clinique : les messages anglais avec chiffres ne
# doivent PAS détourner l'intention ; les salutations restent des
# salutations même longues.
# =====================================================================
from soukna_graph.nodes.orchestrator import heuristic_intent


def test_greeting_fr():
    assert heuristic_intent("Bonjour")["intent"] == "greeting"
    assert heuristic_intent("Salam, comment allez-vous ?")["intent"] == "greeting"


def test_greeting_ar():
    assert heuristic_intent("سلام عليكم")["intent"] == "greeting"


def test_opportunities_fr():
    assert heuristic_intent("Quelles opportunités pour moi aujourd'hui ?")["intent"] == "opportunities"
    assert heuristic_intent("Montre-moi les appels d'offres matchés")["intent"] == "opportunities"


def test_opportunities_english_with_number_not_hijacked():
    # Un chiffre dans un message anglais ne doit pas casser la classification
    assert heuristic_intent("Hello, what opportunities do you have for 2026?")["intent"] == "opportunities"


def test_digest_request_priority_over_opportunities():
    # « synthèse des opportunités » = demande de synthèse (plus précis)
    assert heuristic_intent("Envoie-moi la synthèse des opportunités")["intent"] == "digest_request"


def test_profile_update():
    assert heuristic_intent("Je veux changer mon secteur : Informatique")["intent"] == "profile_update"
    assert heuristic_intent("mettre à jour mon profil")["intent"] == "profile_update"


def test_other():
    assert heuristic_intent("Quel temps fait-il à Casablanca ?")["intent"] == "other"
    assert heuristic_intent("12345")["intent"] == "other"
