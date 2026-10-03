"""Drift: a live expert action that contradicts a learned guardrail, or a changed boundary. Never overwrite:
version the rule and record a disposition (error | exception | local variant | genuine change)."""
import re
from . import guard


def contradictions(rules: list[dict], form: dict) -> list[dict]:
    """Learned blocking rules whose predicate fires on the expert's own saved record."""
    out = []
    for r in rules:
        res = guard.evaluate(r, form)
        if res["fired"] and r["predicate"]["severity"] == "block":
            out.append(res)
    return out


NUM = re.compile(r"\b(\d+|one|two|three|four|five|six)\b", re.I)
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}


def extract_threshold(text: str):
    m = NUM.search(text)
    if not m:
        return None
    v = m.group(1).lower()
    return int(v) if v.isdigit() else WORDS[v]


def boundary_update(rule: dict, field: str, new_value: float, quote: str, ts: float):
    """Change a numeric clause if the expert states a different boundary; keep version history."""
    for c in rule["predicate"]["all"]:
        if c["field"] == field and c["op"] in ("gte", "lt") and float(c["value"]) != float(new_value):
            old = c["value"]
            c["value"] = new_value
            rule.setdefault("versions", []).append({"v": len(rule.get("versions", [])) + 2, "field": field, "old": old,
                                                    "new": new_value, "quote": quote, "ts": ts, "disposition": "pending"})
            return rule["versions"][-1]
    return None
