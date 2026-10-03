from engine import learner as L


def test_evidence_is_kept_only_when_literal_in_the_cited_turn():
    turns = {"S1-T1": "Before blaming the disease, rule out anything somatic, a sore thumb, wrong footwear."}
    ev = L.verify_evidence([{"turn_id": "S1-T1", "span": "rule out anything somatic"}, {"turn_id": "S1-T1", "span": "always sedate first"}, {"turn_id": "S9-T9", "span": "x"}], turns)
    assert [e["span"] for e in ev] == ["rule out anything somatic"]


def test_predicates_are_proposals_validated_against_known_fields_and_values():
    ok = {"severity": "block", "all": [{"field": "occurrences_today", "op": "gte", "value": 3}, {"field": "escalate_to", "op": "eq", "value": "none"}]}
    assert L.valid_predicate(ok)["severity"] == "warn"           # proposals never block
    assert L.valid_predicate({"all": [{"field": "mood", "op": "eq", "value": "sad"}]}) is None
    assert L.valid_predicate({"all": [{"field": "escalate_to", "op": "eq", "value": "wizard"}]}) is None
    assert L.valid_predicate({"all": [{"field": "occurrences_today", "op": "gte", "value": "many"}]}) is None
    assert L.valid_predicate(None) is None
