import json, os
from engine import learned
from engine.session import Session

CARD = {"id": "LC-900", "title": "Retry refused care later is not enough after two refusals", "kind": "decision_rule", "context": "repeated refusal", "action": "change the approach",
        "rationale": "same approach, same result", "exceptions": [], "guardrails": ["Do not keep retrying unchanged"], "escalation": ["psychologist"], "safety_critical": False,
        "cbt": {"formulation": True, "targeted_action": True, "measures_response": False}, "units": ["KU-S03-12"], "sessions": ["S03"], "source_types": ["Expert statement"],
        "evidence": [{"turn_id": "S03-T0093", "span": "a refusal has reasons", "verified": True, "unit_id": "KU-S03-12", "session": "S03"}],
        "evidence_status": "verbatim-verified", "corroboration": 1, "status": "transcript-learned (unreviewed)", "contradictions": [],
        "proposed_predicate": {"severity": "warn", "all": [{"field": "occurrences_today", "op": "gte", "value": 2}, {"field": "intervention", "op": "eq", "value": "no_action"}]}}


def _put(cards):
    learned.learned_path().write_text(json.dumps({"cards": cards, "agenda": []}))


def test_accepted_learned_card_becomes_a_warn_rule_that_never_blocks_or_adds_questions():
    _put([CARD])
    s = Session("capture")
    assert not any(r.get("learned") for r in s.rules)                       # nothing enforced before review
    s.review("LC-900", "confirm", "yes")
    lr = s.rule("LC-900")
    assert lr["learned"] and lr["predicate"]["severity"] == "warn" and lr["reviewed"] == "confirmed"
    assert "LC-900" not in [r["rule_id"] for r in s.workmap()["seeded_rules"]]       # shown in the learned section, not as a seeded rule
    e = s.add_event({"field": "intervention", "value": "no_action", "form": {}})["event"]
    q = s.propose_question(e["id"], {"voice_silent": True, "hands_still": True, "screen_stable": True})["question"]
    assert q is None or q["rule_id"] != "LC-900"                              # learned cards never add live questions
    t = Session("teach"); t.teach_predict("T1", "a")
    r = t.teach_check_save("T1", {"incident_type": "refusal_of_care", "checks": ["pain"], "occurrences_today": 3, "escalate_to": "team_meeting", "intervention": "no_action", "pattern": "new"})
    assert any(w["rule_id"] == "LC-900" for w in r["warnings"]) and r["saved"]  # warns, does not block
    s.review("LC-900", "reset")
    assert not any(x.get("learned") for x in Session("capture").rules)


def test_rejected_or_unknown_learned_cards_are_not_enforced():
    import pytest
    from engine.session import Conflict
    _put([CARD])
    s = Session("capture"); s.review("LC-900", "reject")
    assert not any(r.get("learned") for r in Session("capture").rules)
    with pytest.raises(Conflict): s.review("LC-404", "confirm")
    s.review("LC-900", "reset")


def test_card_without_a_validated_predicate_is_never_executable():
    c = {**CARD, "proposed_predicate": None}
    assert learned.to_rule(c) is None
