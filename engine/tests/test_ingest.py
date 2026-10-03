from engine.ingest import load_units


def test_units_keep_branches_spans_and_exclude_hypotheses_from_gold():
    us = load_units()
    assert len(us) == 77
    assert sum(1 for u in us if not u.gold_eligible) == 7
    assert any(len(u.branches) > 1 for u in us)           # branches preserved, not joined
    assert sum(1 for u in us if u.spans) >= 60
    s13 = next(u for u in us if u.unit_id == "KU-S13-16")
    assert s13.caveat == "" and "refusal" in s13.subtopic.lower()
    cav = next(u for u in us if u.unit_id == "KU-S13-20")
    assert "recollection" in cav.caveat                   # caveat is kept as a caveat
