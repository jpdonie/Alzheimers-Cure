from engine.export import build
from engine.session import Session


def test_export_labels_status_and_stop_conditions_and_omits_rejected():
    s = Session("capture")
    s.review("R4-treatment-routing", "confirm"); s.review("R6-exit-seeking", "reject")
    md = build(s.rules, s.teachback, s.map_version())
    assert "NOT diagnosis or treatment" in md and "R4-treatment-routing" in md
    assert "[CONFIRMED]" in md and "[HYPOTHESIS]" in md
    assert "STOP, do not save when: intervention in ['give_prn_medication', 'request_antipsychotic']" in md
    assert "R6-exit-seeking" not in md                          # a rejected rule is not exported
    assert "Hand over to: Nurse -> coordinating physician -> treating doctor." in md
    for r in s.rules: s.review(r["id"], "reset")
