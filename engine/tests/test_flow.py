import os
os.environ["APPRENTICE_OFFLINE"] = "1"
os.environ["APPRENTICE_COOLDOWN"] = "0"
import json
from pathlib import Path
from engine.session import Session, load_rules
from engine import drift as drift_ext
from engine import guard, slots as S, federated
from engine.privacy import redact

OK = {"voice_silent": True, "hands_still": True, "screen_stable": True}
DATA = Path(__file__).resolve().parents[2] / "data" / "dementia_care_knowledge_deidentified.json"


def test_quote_spans_are_verbatim_in_data():
    d = json.loads(DATA.read_text())
    T = {t["turn_id"]: (t["english_translation"] or t["text"]) for s in d["sessions"] for t in s["dialogue"]}
    for r in load_rules():
        for s in r["sources"]:
            if s["kind"] == "verbatim":
                assert s["quote_span"] in T[s["quote_turn"]], (r["id"], s["quote_span"])


def test_guard_blocks_and_traces():
    rules = load_rules()
    form = {"incident_type": "refusal_of_care", "checks": [], "occurrences_today": 4, "escalate_to": "none", "intervention": "retry_later_same_carer"}
    fired = {f["rule_id"] for f in guard.check_form(rules, form)}
    assert {"R1-somatic-first", "R3-repeat-escalate", "R2-interaction-first"} <= fired
    ok = {**form, "checks": ["pain", "footwear_skin"], "escalate_to": "team_meeting", "intervention": "swap_carer_or_call_psychologist", "pattern": "new"}
    assert not [f for f in guard.check_form(rules, ok) if f["severity"] == "block"]


def test_capture_questions_are_screen_grounded_gated_and_include_guardrail():
    s = Session("capture")
    e1 = s.add_event({"field": "checks", "value": ["pain"], "delta": {"added": "pain"}, "form": {}})["event"]
    # gate closed while typing
    assert s.propose_question(e1["id"], {**OK, "hands_still": False})["question"] is None
    q1 = s.propose_question(e1["id"], OK)["question"]
    assert q1 and q1["event_id"] == e1["id"] and "pain" in q1["text"]
    s.answer(q1["id"], "I always start with pain, but if the resident is in distress and cannot speak I call the nurse right away.")
    e2 = s.add_event({"field": "intervention", "value": "give_prn_medication", "form": {}})["event"]
    q2 = s.propose_question(e2["id"], OK)["question"]
    e3 = s.add_event({"field": "escalate_to", "value": "nurse", "form": {}})["event"]
    q3 = s.propose_question(e3["id"], OK)["question"]
    qs = [q for q in (q1, q2, q3) if q]
    assert len(qs) >= 3 and all(q["event_id"] for q in qs)
    assert any(q["type"] == "guardrail" for q in qs)
    # same event not asked twice
    assert s.propose_question(e3["id"], OK)["question"] is None


def test_answer_updates_slot_state_and_provenance():
    s = Session("capture")
    e = s.add_event({"field": "checks", "value": ["pain"], "delta": {"added": "pain"}, "form": {}})["event"]
    q = s.propose_question(e["id"], OK)["question"]
    r = s.answer(q["id"], "When the resident is clearly frightened by noise, I deal with that first.")
    assert r["transition"]["after"] in ("expert_stated", "confirmed")
    step = s.workmap()["steps"][0]
    assert step["reason"] and step["provenance"][0]["kind"] == "screen" and any(p["kind"] == "transcript" for p in step["provenance"])
    assert step["confidence"]["label"] in ("medium", "high")


def test_dont_know_does_not_advance():
    s = Session("capture")
    e = s.add_event({"field": "intervention", "value": "give_prn_medication", "form": {}})["event"]
    q = s.propose_question(e["id"], OK)["question"]
    before = S.slot_state(s.rule(q["rule_id"]), q["slot"])
    r = s.answer(q["id"], "I'm not sure, I don't know.")
    assert r["dont_know"] and S.slot_state(s.rule(q["rule_id"]), q["slot"]) == before


def test_drift_extension_on_contradicting_save():
    s = Session("capture", drift=drift_ext)
    out = s.add_event({"field": "save", "form": {"incident_type": "refusal_of_care", "checks": [], "occurrences_today": 1, "escalate_to": "none", "intervention": "no_action"}})
    assert out["drift_question"] and out["drift_question"]["type"] == "drift"
    plain = Session("capture")  # core path works without the extension
    assert plain.add_event({"field": "save", "form": {"incident_type": "refusal_of_care", "checks": [], "intervention": "no_action"}})["drift_question"] is None


def test_debrief_gives_three_new_followups_and_teachback():
    s = Session("capture")
    e = s.add_event({"field": "checks", "value": ["pain"], "delta": {"added": "pain"}, "form": {}})["event"]
    q = s.propose_question(e["id"], OK)["question"]; s.answer(q["id"], "Pain first, always.")
    d = s.debrief_start()
    assert len(d["questions"]) >= 3
    seen = {(x["rule_id"], x["slot"], x["rung"]) for x in s.questions if x["phase"] == "capture"}
    assert all((x["rule_id"], x["slot"], x["rung"]) not in seen for x in d["questions"][:3])
    for dq in d["questions"][:3]:
        s.answer(dq["id"], "It depends, call the nurse when unsure.")
    tb = s.teachback_text(); assert tb["steps"]
    for st in tb["steps"]:
        s.confirm(st["rule_id"], True)
    assert s.debrief_status()["teach_back_done"]


def test_teach_blocks_before_save_then_allows_after_fix_and_updates_mastery():
    s = Session("teach")
    bad = {"incident_type": "refusal_of_care", "checks": [], "occurrences_today": 4, "escalate_to": "none", "intervention": "retry_later_same_carer"}
    r = s.teach_check_save("T1", bad)
    assert not r["saved"] and {b["rule_id"] for b in r["blocked"]} >= {"R1-somatic-first", "R3-repeat-escalate"}
    assert r["blocked"][0]["explain"]["expert_words"]
    good = {**bad, "checks": ["pain"], "escalate_to": "team_meeting", "intervention": "swap_carer_or_call_psychologist", "pattern": "new"}
    r2 = s.teach_check_save("T1", good)
    assert r2["saved"] and r2["next_scenario"] in ("T2", "T3")
    row = next(m for m in r2["mastery"] if m["rule_id"] == "R1-somatic-first")
    assert row["mean"] < 0.5 + 1e-9  # failed first attempt counted, hinted retry does not inflate


def test_unseen_exit_seeking_case_is_caught():
    s = Session("teach")
    r = s.teach_check_save("T2", {"incident_type": "exit_seeking", "intervention": "retry_later_same_carer", "checks": [], "occurrences_today": 2, "escalate_to": "none"})
    assert {b["rule_id"] for b in r["blocked"]} == {"R6-exit-seeking"}


def test_off_record_deletes_derived_nodes():
    s = Session("capture")
    e = s.add_event({"field": "intervention", "value": "give_prn_medication", "form": {}})["event"]
    q = s.propose_question(e["id"], OK)["question"]; s.answer(q["id"], "Never alone, always the nurse.")
    t = s.off_record(0.0)
    assert t["events"] == 1 and t["answers"] == 1 and not s.answers and not s.events
    assert S.slot_state(s.rule(q["rule_id"]), q["slot"]) in ("hypothesized", "missing")


def test_redaction_and_dp():
    t, n = redact("Call Mrs Smith on +49 170 1234567 or a@b.com")
    assert n >= 3 and "Smith" not in t and "@" not in t
    sw = federated.sweep(trials=20)
    assert sw[0]["mae"] > sw[-1]["mae"]
