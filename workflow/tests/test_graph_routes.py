# =====================================================================
# Routage du graphe : les deux modes (pipeline / chat) et les court-cuits.
# =====================================================================
from soukna_graph.graph import _after_digest, _route_from_intake, _route_from_orchestrator


def test_intake_routes_pipeline():
    assert _route_from_intake({"route": "pipeline"}) == "pipeline"


def test_intake_routes_chat():
    assert _route_from_intake({"route": "process_message"}) == "orchestrator"


def test_intake_short_circuits_duplicates_and_ignored():
    assert _route_from_intake({"route": "duplicate_message"}) == "end"
    assert _route_from_intake({"route": "ignored_event"}) == "end"


def test_orchestrator_routes_analysis_intents_to_matching():
    assert _route_from_orchestrator({"intent": "opportunities"}) == "matching"
    assert _route_from_orchestrator({"intent": "digest_request"}) == "matching"


def test_orchestrator_routes_faq_intents_to_faq_node():
    assert _route_from_orchestrator({"intent": "faq"}) == "faq"


def test_orchestrator_routes_other_intents_to_response():
    assert _route_from_orchestrator({"intent": "greeting"}) == "response"
    assert _route_from_orchestrator({"intent": "profile_update"}) == "response"
    assert _route_from_orchestrator({"intent": "other"}) == "response"


def test_after_digest_pipeline_ends():
    assert _after_digest({"run_pipeline": True}) == "end"


def test_after_digest_chat_goes_to_response():
    assert _after_digest({}) == "response"
