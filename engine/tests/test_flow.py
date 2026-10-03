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
    s.teach_predict("T1", "a")
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
    s.teach_predict("T2", "a")
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


def test_vision_caption_is_budgeted_and_degrades_without_provider(monkeypatch):
    from engine import llm
    s = Session("capture")
    e = s.add_event({"field": "checks", "value": ["pain"], "delta": {"added": "pain"}, "form": {}})["event"]
    assert s.add_frame(e["id"], "data:image/jpeg;base64,AAAA") is None and s.degraded   # offline: no caption, explicit degrade
    s2 = Session("capture")
    monkeypatch.setattr(llm, "vision", lambda *a, **k: "The pain checkbox is ticked for Mrs Smith.")
    e2 = s2.add_event({"field": "checks", "value": ["pain"], "form": {}})["event"]
    cap = s2.add_frame(e2["id"], "data:image/jpeg;base64,AAAA")
    assert cap and "Smith" not in cap and e2["id"] in s2.frames
    e3 = s2.add_event({"field": "observation", "value": "x", "form": {}})["event"]
    assert s2.add_frame(e3["id"], "data:image/jpeg;base64,AAAA") is None   # not a decision-relevant field


def test_seeded_guardrails_are_not_relabelled_as_expert_stated():
    s = Session("capture")
    e = s.add_event({"field": "intervention", "value": "give_prn_medication", "form": {}})["event"]
    q = s._mk_question(s.rule("R4-treatment-routing"), "guardrails", 0, e)       # a guardrail-slot question, whichever the ranker picks
    seeded = [g["text"] for g in s.rule(q["rule_id"])["slots"]["guardrails"]]
    s.answer(q["id"], "Never alone; the nurse decides every time.")
    items = s.rule(q["rule_id"])["slots"]["guardrails"]
    for g in items:
        if g["text"] in seeded:
            assert g["state"] == "hypothesized" and not g.get("live")      # untouched seed
    assert any(g.get("live") and g["state"] == "expert_stated" for g in items)  # only the new item carries live provenance


def test_dataset_summaries_are_never_presented_as_quotations():
    s = Session("teach")
    ex = s._explain(s.rule("R4-treatment-routing"))          # R4 sources are dataset summaries only
    assert not [w for w in ex["expert_words"] if w["kind"] == "transcript"]
    assert ex["dataset_summaries"] and all("summary" in d for d in ex["dataset_summaries"])
    ex1 = s._explain(s.rule("R1-somatic-first"))
    assert ex1["expert_words"] and all(w["kind"] in ("screen", "transcript") for w in ex1["expert_words"])


def test_off_the_record_stops_collection_server_side():
    import pytest
    from engine.session import Conflict
    s = Session("capture")
    e = s.add_event({"field": "checks", "value": ["pain"], "delta": {"added": "pain"}, "form": {}})["event"]
    s.set_recording(False)
    for call in (lambda: s.add_event({"field": "checks", "value": [], "form": {}}), lambda: s.add_frame(e["id"], "data:image/jpeg;base64,AA"),
                 lambda: s.propose_question(e["id"], OK)):
        with pytest.raises(Conflict):
            call()
    s.set_recording(True)
    assert s.propose_question(e["id"], OK)["question"] is not None


def test_superseded_event_is_not_asked_about():
    s = Session("capture")
    old = s.add_event({"field": "checks", "value": ["pain"], "delta": {"added": "pain"}, "form": {}})["event"]
    s.add_event({"field": "intervention", "value": "give_prn_medication", "form": {}})
    r = s.propose_question(old["id"], OK)
    assert r["question"] is None and "fresh" in r["reason"]


def test_impossible_transitions_are_rejected():
    import pytest
    from engine.session import Conflict
    s = Session("capture")
    e = s.add_event({"field": "intervention", "value": "give_prn_medication", "form": {}})["event"]
    q = s.propose_question(e["id"], OK)["question"]; s.answer(q["id"], "The nurse decides.")
    with pytest.raises(Conflict): s.answer(q["id"], "again")                       # double submission
    untouched = next(r["id"] for r in s.rules if not any(x["rule_id"] == r["id"] and x["phase"] == "capture" for x in s.questions))
    with pytest.raises(Conflict): s.confirm(untouched, True)                       # nothing captured for that rule
    t = Session("teach")
    with pytest.raises(Conflict): t.teach_check_save("T1", {})                     # save before prediction
    t.teach_predict("T1", "b")
    with pytest.raises(Conflict): t.teach_predict("T1", "a")                       # one prediction per case


def test_teach_consumes_a_frozen_artifact():
    import pytest
    from engine.session import Conflict
    t = Session("teach"); t.freeze(); t.teach_predict("T1", "b")
    t.rule("R1-somatic-first")["slots"]["guardrails"].append({"text": "tampered", "state": "expert_stated"})
    with pytest.raises(Conflict):
        t.teach_check_save("T1", {"incident_type": "refusal_of_care", "checks": []})


def test_scope_blocks_clinical_language_without_human_escalation():
    t = Session("teach"); t.teach_predict("T1", "b")
    ok_form = {"incident_type": "refusal_of_care", "checks": ["pain"], "occurrences_today": 1, "escalate_to": "none", "intervention": "swap_carer_or_call_psychologist", "pattern": "new",
               "observation": "Resident choking on food during lunch"}
    r = t.teach_check_save("T1", ok_form)
    assert not r["saved"] and r["blocked"][-1]["guardrail_id"] == "SCOPE-clinical-escalation"
    r2 = t.teach_check_save("T1", {**ok_form, "escalate_to": "nurse"})
    assert r2["saved"]


def test_workmap_lists_demonstrated_events_without_explanations():
    s = Session("capture")
    s.add_event({"field": "observation", "value": "refuses tray", "form": {}})
    wm = s.workmap()
    assert wm["unexplained_events"] and wm["unexplained_events"][0]["text"].startswith("changed observation")


def test_pain_and_swelling_language_requires_a_human_route():
    from engine import scope
    assert scope.classify("she is in pain and her foot is swollen")["escalate"]
    assert not scope.classify("refused the tray, hearing aids were in the drawer")["escalate"]
    t = Session("teach"); t.teach_predict("T1", "b")
    form = {"incident_type": "refusal_of_care", "checks": ["pain"], "occurrences_today": 1, "escalate_to": "psychologist", "intervention": "swap_carer_or_call_psychologist",
            "pattern": "new", "observation": "She cried out, pain in the left foot"}
    assert t.teach_check_save("T1", form)["blocked"][-1]["guardrail_id"] == "SCOPE-clinical-escalation"
    assert t.teach_check_save("T1", {**form, "escalate_to": "team_meeting"})["saved"]


def test_map_confirmed_requires_every_live_step():
    s = Session("capture")
    for field, val in (("checks", ["pain"]), ("intervention", "give_prn_medication")):
        e = s.add_event({"field": field, "value": val, "delta": {"added": "pain"} if field == "checks" else None, "form": {}})["event"]
        q = s.propose_question(e["id"], OK)["question"]; s.answer(q["id"], "The nurse decides.")
    steps = s.workmap()["steps"]; assert len(steps) >= 2
    s.confirm(steps[0]["rule_id"], True)
    assert not s._map_confirmed()                       # partial confirmation is not confirmation
    for st in steps[1:]: s.confirm(st["rule_id"], True)
    assert s._map_confirmed()


def test_abstains_when_the_incident_type_is_outside_learned_knowledge():
    t = Session("teach"); t.teach_predict("T1", "b")
    form = {"incident_type": "other", "checks": [], "occurrences_today": 1, "escalate_to": "none", "intervention": "no_action", "pattern": "new"}
    r = t.teach_check_save("T1", form)
    assert not r["saved"] and r["blocked"][-1]["guardrail_id"] == "ABSTAIN-outside-knowledge"
    assert t.teach_check_save("T1", {**form, "escalate_to": "team_meeting"})["saved"]       # a human route resolves the abstention
