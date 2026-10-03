import json
from engine import graph, learned
from engine.session import Session, load_rules
from engine.tests.test_learned import CARD

OK = {"voice_silent": True, "hands_still": True, "screen_stable": True}


def _types(g, t): return [n for n in g["nodes"] if n["type"] == t]


def test_graph_has_rules_guardrails_fields_routes_and_evidence_edges():
    learned.learned_path().write_text(json.dumps({"cards": [], "agenda": []}))
    g = graph.build(Session("capture"))
    ids = {n["id"] for n in g["nodes"]}
    assert {f"rule:{r['id']}" for r in load_rules()} <= ids
    assert len(_types(g, "guardrail")) >= 5 and {"field:checks", "field:escalate_to"} <= ids
    # R4 names an ordered route: nurse -> coordinating physician -> treating doctor
    then = {(e["source"], e["target"]) for e in g["edges"] if e["type"] == "then"}
    assert ("route:nurse", "route:coordinating_physician") in then and ("route:coordinating_physician", "route:treating_doctor") in then
    cites = [e for e in g["edges"] if e["type"] == "cites" and e["source"] == "rule:R4-treatment-routing"]
    assert cites and all(e["label"] == "dataset summary" for e in cites)          # summaries are labelled as such in the graph too
    r1 = [e for e in g["edges"] if e["type"] == "cites" and e["source"] == "rule:R1-somatic-first"]
    assert r1 and all(e["label"] == "verbatim" for e in r1)
    assert all(e["source"] in ids and e["target"] in ids for e in g["edges"])      # no dangling edges


def test_live_capture_adds_a_moment_node_and_review_changes_status():
    learned.learned_path().write_text(json.dumps({"cards": [], "agenda": []}))
    s = Session("capture")
    e = s.add_event({"field": "intervention", "value": "give_prn_medication", "form": {}})["event"]
    q = s.propose_question(e["id"], OK)["question"]; s.answer(q["id"], "The nurse decides.")
    g = graph.build(s)
    assert _types(g, "moment") and any(x["type"] == "seen_live" for x in g["edges"])
    status = lambda g, rid: next(n["status"] for n in g["nodes"] if n["id"] == f"rule:{rid}")
    rid = q["rule_id"]                                    # whichever rule the ranker asked about
    assert status(g, rid) == "live"
    s.review(rid, "confirm"); assert status(graph.build(s), rid) == "confirmed"
    s.review(rid, "reject"); assert status(graph.build(s), rid) == "rejected"
    s.review(rid, "reset")


def test_learned_cards_connect_to_units_and_rederive_curated_rules():
    card = {**CARD, "id": "LC-901", "units": ["KU-S03-10"], "proposed_predicate": {"severity": "warn", "all": [{"field": "occurrences_today", "op": "gte", "value": 3}, {"field": "escalate_to", "op": "neq", "value": "team_meeting"}]}}
    learned.learned_path().write_text(json.dumps({"cards": [card], "agenda": []}))
    g = graph.build(Session("capture"))
    assert any(n["id"] == "learned:LC-901" for n in g["nodes"])
    assert any(e["type"] == "learned_from" and e["source"] == "learned:LC-901" and e["target"] == "unit:KU-S03-10" for e in g["edges"])
    assert any(e["type"] == "re_derives" and e["target"] == "rule:R3-repeat-escalate" for e in g["edges"])
    assert g["stats"]["rules_rederived_by_learner"] == ["R3-repeat-escalate"]
    learned.learned_path().write_text(json.dumps({"cards": [], "agenda": []}))


def test_rederives_ignores_the_generic_refusal_clause():
    refusal = {"all": [{"field": "incident_type", "op": "eq", "value": "refusal_of_care"}]}
    r3 = next(r for r in load_rules() if r["id"] == "R3-repeat-escalate")["predicate"]
    assert not graph.rederives(refusal, r3)                                          # shared only by nearly every rule
    assert graph.rederives({"all": [{"field": "occurrences_today", "op": "gte", "value": 3}]}, r3)
