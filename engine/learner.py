"""Transcript learner: the apprentice reads every gold-eligible interview unit and learns decision cards
[context -> action -> rationale -> exceptions -> guardrails -> escalation] with VERBATIM evidence verified by code.
Batched iterations: (1) extract per unit, (2) merge across units/sessions, (3) gap scan + contradiction check.
Nothing here is expert-confirmed: every card is a `transcript-learned` hypothesis until a person reviews it.
  python -m engine.learner extract | merge | report"""
import json, re, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np

from . import llm
from .ingest import Unit, load_units

DATA = Path(__file__).resolve().parent.parent / "data"
RAW, LEARNED, REPORT = DATA / "learner_raw.json", DATA / "learned_map.json", DATA / "learner_report.json"
KINDS = {"decision_rule", "escalation_rule", "principle", "process", "measurement", "other"}
FIELDS = {"incident_type": {"refusal_of_care", "exit_seeking", "medication_request", "other"},
          "checks": {"pain", "footwear_skin", "hunger_thirst", "hearing_vision_aids", "noise_environment", "toileting"},
          "pattern": {"new", "habitual", "unsure"},
          "intervention": {"no_action", "retry_later_same_carer", "swap_carer_or_call_psychologist", "reassure_and_note", "give_prn_medication", "adjust_diet", "integration_plan_review"},
          "escalate_to": {"none", "nurse", "psychologist", "team_meeting", "coordinating_physician"}, "occurrences_today": None}
OPS = {"eq", "neq", "in", "not_in", "contains", "not_contains", "gte", "lt"}

SYSTEM = f"""You are an apprentice learning from interviews with experts in psychologist-led, non-drug dementia care in nursing homes.
From ONE knowledge unit, extract decision cards ONLY for what an expert states or corrects. Never turn interviewer assumptions into rules. Never invent facts: leave strings empty and lists empty when not stated.
Return JSON {{"cards":[...]}}. Each card:
- title (max 12 words)
- kind: one of decision_rule (if X then do/avoid Y), escalation_rule (who to involve and when), principle (general belief with no concrete condition), process (how the team/organisation works), measurement (how something is measured), other
- context, action, rationale (short, expert's terms), exceptions (list: when NOT), guardrails (list: limits, never-do, stop-and-ask), escalation (who, else "")
- safety_critical (true when pain, medication, injury, restraint, acute deterioration or other clinical risk is involved)
- cbt: {{"formulation": bool, "targeted_action": bool, "measures_response": bool}} (does the card state what drives the problem / a specific intervention / how the response is checked)
- evidence: list of {{"turn_id", "span"}} where span is an EXACT contiguous substring copied from that turn's text (max 220 chars), preferring the expert's words
- proposed_predicate (optional): ONLY if the situation where the rule is VIOLATED can be checked on a care-record form with fields {{"incident_type": {sorted(FIELDS['incident_type'])}, "checks": list containing any of {sorted(FIELDS['checks'])}, "occurrences_today": integer, "pattern": {sorted(FIELDS['pattern'])}, "intervention": {sorted(FIELDS['intervention'])}, "escalate_to": {sorted(FIELDS['escalate_to'])}}}: {{"severity":"warn","all":[{{"field":..,"op":one of {sorted(OPS)},"value":..}}]}}. Omit when not expressible.
Prefer 1 to 3 cards; zero if the unit holds no expert-stated knowledge."""


def _norm(t: str) -> str: return re.sub(r"\s+", " ", t).strip()


def verify_evidence(evidence: list[dict], turns: dict[str, str]) -> list[dict]:
    """Keep only spans that are literal substrings of the cited turn (whitespace-normalised)."""
    out = []
    for e in evidence or []:
        t, sp = turns.get(e.get("turn_id", "")), _norm(str(e.get("span", "")))
        if t and sp and sp in _norm(t):
            out.append({"turn_id": e["turn_id"], "span": sp, "verified": True})
    return out


def valid_predicate(p) -> dict | None:
    """Predicates are proposals: accepted only if every clause uses known fields, ops and enum values."""
    try:
        if not isinstance(p, dict) or not p.get("all"):
            return None
        for c in p["all"]:
            f, op, v = c["field"], c["op"], c["value"]
            if f not in FIELDS or op not in OPS:
                return None
            allowed = FIELDS[f]
            vals = v if isinstance(v, list) else [v]
            if allowed is None:
                if not all(isinstance(x, (int, float)) for x in vals):
                    return None
            elif not all(x in allowed for x in vals):
                return None
        return {"severity": "warn", "all": p["all"]}
    except (KeyError, TypeError):
        return None


def extract_unit(u: Unit) -> dict:
    turns = {s.turn_ids[0]: s.text for s in u.spans}
    body = "\n".join(f"[{tid}] {txt[:1400]}" for tid, txt in turns.items())
    user = (f"Unit {u.unit_id} (session {u.session}, {u.source_type}). Subtopic: {u.subtopic}\nDataset summary of the expert answer: {u.answer[:900]}\n"
            f"Dataset practice rules: {u.branches}\nCaveat: {u.caveat}\n\nTurns:\n{body}")
    try:
        raw = llm.complete_json(SYSTEM, user, llm.SMART, 1800)
    except Exception as e:
        return {"unit_id": u.unit_id, "error": str(e)[:120], "cards": []}
    cards = []
    for c in (raw.get("cards") or [])[:4]:
        ev_all = c.get("evidence") or []
        ev = verify_evidence(ev_all, turns)
        cards.append({
            "unit_id": u.unit_id, "session": u.session, "source_type": u.source_type, "title": str(c.get("title", ""))[:120],
            "kind": c.get("kind") if c.get("kind") in KINDS else "other", "context": str(c.get("context", "")), "action": str(c.get("action", "")),
            "rationale": str(c.get("rationale", "")), "exceptions": [str(x) for x in c.get("exceptions") or []][:6],
            "guardrails": [str(x) for x in c.get("guardrails") or []][:6], "escalation": str(c.get("escalation", "")),
            "safety_critical": bool(c.get("safety_critical")), "cbt": {k: bool((c.get("cbt") or {}).get(k)) for k in ("formulation", "targeted_action", "measures_response")},
            "evidence": ev, "evidence_claimed": len(ev_all), "evidence_status": "verbatim-verified" if ev else "summary-only",
            "proposed_predicate": valid_predicate(c.get("proposed_predicate")), "caveat": u.caveat})
    return {"unit_id": u.unit_id, "cards": cards}


def extract(workers: int = 4):
    units = [u for u in load_units() if u.gold_eligible and (u.answer or u.branches)]
    done = json.loads(RAW.read_text()) if RAW.exists() else {}
    todo = [u for u in units if u.unit_id not in done]
    print(len(units), "units;", len(todo), "to extract", flush=True)
    with ThreadPoolExecutor(workers) as ex:
        for r in ex.map(extract_unit, todo):
            if not r.get("error"):
                done[r["unit_id"]] = r
            else:
                print("error", r["unit_id"], r["error"], flush=True)
            RAW.write_text(json.dumps(done))
    print(sum(len(v["cards"]) for v in done.values()), "cards from", len(done), "units", llm.usage_summary())


# ---------------- merge across units and sessions
def _vec(cards):
    from sklearn.feature_extraction.text import TfidfVectorizer
    docs = [f"{c['title']}. {c['context']} {c['action']}" for c in cards]
    v = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True).fit(docs)
    return v.transform(docs)


CLUSTER = ("You group knowledge cards extracted from different interviews. Cards belong in the same group only if they state the SAME underlying guidance, "
           "or one is a direct specific instance of the other (for example 'check for pain' and 'rule out somatic causes first'). Related topic alone is not enough. "
           "Every index must appear in exactly one group. JSON: {\"groups\": [[0,3],[1],...]}")
SPECIFIC = ["decision_rule", "escalation_rule", "measurement", "process", "principle", "other"]


def _cluster_llm(cards) -> list[list[int]] | None:
    lines = "\n".join(f"{i} | {c['session']} | {c['kind']} | {c['title']} | {c['action'][:110]}" for i, c in enumerate(cards))
    try:
        g = llm.complete_json(CLUSTER, lines, llm.SMART, 4000)["groups"]
    except Exception:
        return None
    seen = [i for grp in g for i in grp]
    if sorted(seen) != list(range(len(cards))):          # reject any clustering that drops or duplicates a card
        return None
    return [list(map(int, grp)) for grp in g]


def merge(threshold: float = 0.42):
    raw = json.loads(RAW.read_text())
    cards = [c for r in raw.values() for c in r["cards"]]
    cards = [c for c in cards if c["title"] and (c["action"] or c["guardrails"] or c["exceptions"])]
    n = len(cards)
    clustered = _cluster_llm(cards)
    if clustered is None:                                  # fallback: lexical similarity (weak, but offline)
        M = _vec(cards); sim = (M @ M.T).toarray(); parent = list(range(n))
        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]; i = parent[i]
            return i
        for i in range(n):
            for j in range(i + 1, n):
                if sim[i, j] >= threshold and cards[i]["kind"] == cards[j]["kind"]:
                    parent[find(j)] = find(i)
        gmap: dict[int, list[int]] = {}
        for i in range(n): gmap.setdefault(find(i), []).append(i)
        clustered = list(gmap.values())
    groups = {k: g for k, g in enumerate(clustered)}
    out = []
    for k, idx in enumerate(sorted(groups.values(), key=lambda g: -len(g))):
        g = [cards[i] for i in idx]; lead = max(g, key=lambda c: len(c["evidence"]) * 3 + len(c["guardrails"]) + len(c["exceptions"]))
        kind = min((c["kind"] for c in g), key=SPECIFIC.index)   # the most specific kind in the group
        uniq = lambda xs: list(dict.fromkeys(x for x in xs if x))
        out.append({
            "id": f"LC-{k + 1:03d}", "title": lead["title"], "kind": kind, "context": lead["context"], "action": lead["action"], "rationale": lead["rationale"],
            "exceptions": uniq(x for c in g for x in c["exceptions"]), "guardrails": uniq(x for c in g for x in c["guardrails"]),
            "escalation": uniq(c["escalation"] for c in g), "safety_critical": any(c["safety_critical"] for c in g),
            "cbt": {k2: any(c["cbt"][k2] for c in g) for k2 in ("formulation", "targeted_action", "measures_response")},
            "units": sorted({c["unit_id"] for c in g}), "sessions": sorted({c["session"] for c in g}),
            "source_types": sorted({c["source_type"] for c in g}),
            "evidence": [{**e, "unit_id": c["unit_id"], "session": c["session"]} for c in g for e in c["evidence"]][:6],
            "evidence_status": "verbatim-verified" if any(c["evidence"] for c in g) else "summary-only",
            "proposed_predicate": next((c["proposed_predicate"] for c in g if c["proposed_predicate"]), None),
            "corroboration": len({c["session"] for c in g}), "status": "transcript-learned (unreviewed)", "contradictions": []})
    LEARNED.write_text(json.dumps({"version": "learned-1", "n_cards_raw": n, "cards": out}, indent=1))
    print(n, "raw cards ->", len(out), "merged cards;", sum(1 for c in out if c["corroboration"] >= 2), "corroborated by 2+ sessions")


CONTRA = ("Two excerpts of expert statements about the same care situation follow. Do they CONTRADICT each other in what to do, or in a numeric/boundary limit? "
          "Differences in emphasis are not contradictions. JSON: {\"contradiction\": bool, \"why\": \"one sentence\"}")


def contradictions():
    """Cross-session drift in the corpus itself: within corroborated clusters, ask whether two sessions disagree."""
    d = json.loads(LEARNED.read_text()); found = 0
    raw = json.loads(RAW.read_text()); by_unit = {u: r["cards"] for u, r in raw.items()}
    for c in d["cards"]:
        if c["corroboration"] < 2 or c["kind"] not in ("decision_rule", "escalation_rule"):
            continue
        per_session = {}
        for u in c["units"]:
            for card in by_unit.get(u, []):
                if card["title"] and (card["action"] or card["guardrails"]):
                    per_session.setdefault(card["session"], card)
        ss = sorted(per_session)
        for a in range(len(ss)):
            for b in range(a + 1, len(ss)):
                x, y = per_session[ss[a]], per_session[ss[b]]
                try:
                    r = llm.complete_json(CONTRA, f"A ({x['session']}): {x['context']} -> {x['action']} Guardrails: {x['guardrails']}\nB ({y['session']}): {y['context']} -> {y['action']} Guardrails: {y['guardrails']}", llm.FAST, 200)
                except Exception:
                    continue
                if r.get("contradiction"):
                    c["contradictions"].append({"a": x["session"], "b": y["session"], "why": str(r.get("why", ""))[:240]}); found += 1
    LEARNED.write_text(json.dumps(d, indent=1)); print(found, "cross-session contradictions flagged (LLM-judged, unreviewed)")


# ---------------- gap scan over the learned map -> agenda for the next live debrief
def gaps(k: int = 12):
    d = json.loads(LEARNED.read_text()); out = []
    for c in d["cards"]:
        if c["kind"] not in ("decision_rule", "escalation_rule", "principle"):
            continue
        miss = [s for s, v in (("exceptions", c["exceptions"]), ("guardrails", c["guardrails"]), ("escalation", c["escalation"])) if not v]
        if not miss:
            continue
        risk = 3 if c["safety_critical"] else 2 if c["kind"] != "principle" else 1
        out.append({"card": c["id"], "title": c["title"], "missing": miss, "risk": risk, "score": risk * len(miss) * (1 + 0.2 * c["corroboration"]),
                    "ask": {"exceptions": f"When would you NOT: {c['action'][:90]}?", "guardrails": f"What would make you stop before: {c['action'][:90]}?",
                            "escalation": f"Who do you hand this to, and when: {c['title']}?"}[miss[0]]})
    out.sort(key=lambda g: -g["score"]); d["agenda"] = out[:k]; LEARNED.write_text(json.dumps(d, indent=1)); print(len(out), "gaps;", "top", len(d["agenda"]), "kept")


def report():
    d = json.loads(LEARNED.read_text()); cs = d["cards"]
    from collections import Counter
    rep = {"merged_cards": len(cs), "raw_cards": d["n_cards_raw"], "by_kind": dict(Counter(c["kind"] for c in cs)),
           "verbatim_verified": sum(c["evidence_status"] == "verbatim-verified" for c in cs), "safety_critical": sum(c["safety_critical"] for c in cs),
           "with_guardrails": sum(bool(c["guardrails"]) for c in cs), "with_exceptions": sum(bool(c["exceptions"]) for c in cs), "with_escalation": sum(bool(c["escalation"]) for c in cs),
           "corroborated_2plus_sessions": sum(c["corroboration"] >= 2 for c in cs), "with_proposed_predicate": sum(bool(c["proposed_predicate"]) for c in cs),
           "contradictions": sum(len(c["contradictions"]) for c in cs), "cbt_formulation": sum(c["cbt"]["formulation"] for c in cs),
           "cbt_targeted_action": sum(c["cbt"]["targeted_action"] for c in cs), "cbt_measures_response": sum(c["cbt"]["measures_response"] for c in cs),
           "cbt_all_three": sum(all(c["cbt"].values()) for c in cs), "agenda": d.get("agenda", [])[:5], "usage": llm.usage_summary()}
    REPORT.write_text(json.dumps(rep, indent=1)); print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    {"extract": extract, "merge": merge, "contradictions": contradictions, "gaps": gaps, "report": report}[sys.argv[1]]()
