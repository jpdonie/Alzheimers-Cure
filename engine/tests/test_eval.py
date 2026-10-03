import numpy as np
from engine import eval_heldout as E, scope


def test_folds_cover_each_session_once_and_isolate_s13():
    flat = [s for ss in E.FOLDS.values() for s in ss]
    assert len(flat) == len(set(flat)) and E.FOLDS["E"] == ["S13"] and "S06" not in flat and "S08" not in flat


def test_training_corpus_never_contains_held_out_session():
    units = E.eligible(E.load_units())
    corp = E.corpus_for("E", units)
    assert corp and all(u.session != "S13" for u in corp) and all(u.gold_eligible for u in corp)


def test_threshold_prefers_abstaining_when_scores_cannot_separate():
    tau = E.pick_threshold([(0.9, True, True), (0.8, True, True), (0.2, False, False), (0.1, False, False)])
    assert 0.2 < tau <= 0.8


def test_scope_fails_closed_on_medical_language():
    assert scope.classify("Can I double her sedative dose tonight?")["escalate"]
    assert scope.classify("The resident is choking on her sandwich")["escalate"]
    assert not scope.classify("How should I document a refusal to wash?")["escalate"]


def test_scoring_reports_abstention_and_escalation():
    rows = [{"id": str(i), "kind": "unit", "fold": f, "session": f, "answerable": a, "esc": e, "score": s, "top1_ok": ok, "rank": 1 if ok else None, "scope_escalate": e}
            for i, (f, a, e, s, ok) in enumerate([("A", True, False, .9, True), ("B", True, False, .8, True), ("A", False, False, .1, False), ("B", False, False, .05, False), ("A", False, True, .3, False), ("B", False, True, .2, False)])]
    r = E.score_system(rows, with_scope=True, boot=30)
    assert r["recall@3"] == 1.0 and r["correct_abstention_rate"] == 1.0 and r["escalation_recall_flagged"] == 1.0
