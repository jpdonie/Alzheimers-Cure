from engine.ingest import load_rules


def test_all_rules_have_provenance():
    rules = load_rules()
    assert len(rules) == 77
    assert all(r.provenance and r.provenance[0].turn_ids is not None for r in rules)
