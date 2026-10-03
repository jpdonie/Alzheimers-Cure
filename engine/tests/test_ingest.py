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


def test_related_knowledge_comes_from_uncited_gold_units():
    from engine.related import related
    from engine.session import load_rules
    r1 = next(r for r in load_rules() if r["id"] == "R1-somatic-first")
    rel = related(r1)
    cited = {s["unit_id"] for s in r1["sources"]}
    gold = {u.unit_id for u in load_units() if u.gold_eligible}
    assert rel and all(x["unit_id"] not in cited and x["unit_id"] in gold for x in rel)
    assert all(x["branches"] is not None for x in rel)
