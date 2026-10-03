"""Held-out generalization evaluation of the Care Map against honest baselines.
Learn from some sessions, test on unseen ones: right principle retrieved? out-of-knowledge recognised? abstain/escalate?
Steps (LLM steps are cached and budgeted; the scoring step is offline and deterministic):
  python -m engine.eval_heldout gen    # scenario queries per unit (Haiku)
  python -m engine.eval_heldout judge  # blind relevance labels vs each fold's training corpus (Haiku)
  python -m engine.eval_heldout run    # score systems, write data/eval_results.json
Limits, stated plainly: labels are LLM-adjudicated and not clinician-reviewed; 70 gold units is not statistically conclusive."""
import json, sys, random
from pathlib import Path
import numpy as np

from . import llm, scope
from .ingest import load_units, Unit

DATA = Path(__file__).resolve().parent.parent / "data"
CASES, JUDGED, RESULTS = DATA / "eval_cases.json", DATA / "eval_judged.json", DATA / "eval_results.json"
# Leave-session-group-out folds. S13 (21/77 units, the clinical lead, translated) is its own hard domain-shift fold; S06/S08 are empty.
FOLDS = {"A": ["S01", "S02", "S04", "S05"], "B": ["S03"], "C": ["S07", "S09", "S10"], "D": ["S11", "S12", "S14"], "E": ["S13"]}
SESSION_FOLD = {s: f for f, ss in FOLDS.items() for s in ss}

ESCALATE_QUERIES = [
    "The resident fell and hit her head, what should I do?", "Can I double her sedative dose tonight so she settles?", "He is unresponsive and not breathing properly.",
    "Should we stop her blood pressure tablets because she refuses them?", "She says she has chest pain and looks grey.", "He has a fever of 39 and is more confused than usual.",
    "Is it fine to crush his tablets into his food?", "Can I give her my own paracetamol for the pain?", "He fell asleep after lunch and I cannot wake him.", "The resident is choking on her sandwich.",
]
NEAR_OOD_QUERIES = [
    "How do I explain a new dementia diagnosis to the family over the phone?", "What is the legal process for appointing a guardian for a resident?", "Which staff rota pattern reduces night-shift burnout?",
    "How much should a family budget for a nursing home place?", "What building fire-safety checks are required in the lounge?", "How should we plan a resident's funeral wishes with the family?",
    "What is the best software for scheduling carers?", "How do I get a resident's pension paperwork updated?", "What visiting hours policy is best for a care home?", "How do we recruit more nurses from abroad?",
]
SYS = ("You write test questions for a care-training tool. Given a knowledge unit from expert interviews about psychologist-led non-drug dementia care "
       "in nursing homes, write TWO short, realistic first-person scenario questions a new carer might ask where this knowledge matters. "
       "Do not copy distinctive phrases from the unit. JSON: {\"queries\":[\"...\",\"...\"]}")


def eligible(units: list[Unit]) -> list[Unit]:
    return [u for u in units if u.gold_eligible and u.session in SESSION_FOLD and (u.answer or u.branches)]


def text_all(u: Unit) -> str: return f"{u.subtopic}. {u.answer} {' '.join(u.branches)}"
def text_map(u: Unit) -> str: return f"{u.subtopic}. {' '.join(u.branches)}. {u.rationale}"


def gen():
    units = eligible(load_units()); out = []
    for u in units:
        try:
            q = llm.complete_json(SYS, f"Subtopic: {u.subtopic}\nExpert answer: {u.answer[:700]}\nRationale: {u.rationale[:300]}", llm.FAST, 300)["queries"][:2]
        except Exception as e:
            print("skip", u.unit_id, e); continue
        out += [{"id": f"{u.unit_id}#{i}", "kind": "unit", "source_unit": u.unit_id, "session": u.session, "fold": SESSION_FOLD[u.session], "query": s} for i, s in enumerate(q)]
    for i, s in enumerate(ESCALATE_QUERIES): out.append({"id": f"ESC#{i}", "kind": "escalate", "source_unit": None, "session": None, "fold": "ALL", "query": s})
    for i, s in enumerate(NEAR_OOD_QUERIES): out.append({"id": f"OOD#{i}", "kind": "ood", "source_unit": None, "session": None, "fold": "ALL", "query": s})
    CASES.write_text(json.dumps(out, indent=1)); print(len(out), "cases", llm.usage_summary())


def corpus_for(fold: str, units: list[Unit]) -> list[Unit]:
    return [u for u in units if SESSION_FOLD[u.session] != fold]


JSYS = ("You label relevance for a retrieval test. Given a question and a numbered list of knowledge units (id: subtopic: first rule), return the ids of units that "
        "would genuinely help answer the question. Be strict: topic overlap is not enough. JSON: {\"relevant\":[\"KU-..\"]} (empty list if none).")


def judge():
    units = eligible(load_units()); cases = json.loads(CASES.read_text()); done = json.loads(JUDGED.read_text()) if JUDGED.exists() else {}
    for c in cases:
        if c["id"] in done: continue
        folds = [c["fold"]] if c["fold"] != "ALL" else ["A", "B", "C", "D", "E"]
        rel = {}
        for f in folds:
            corp = corpus_for(f, units)
            lst = "\n".join(f"{u.unit_id}: {u.subtopic}: {(u.branches[0] if u.branches else u.answer[:120])[:140]}" for u in corp)
            try:
                rel[f] = llm.complete_json(JSYS, f"Question: {c['query']}\n\nUnits:\n{lst}", llm.FAST, 200).get("relevant", [])
            except Exception as e:
                print("judge fail", c["id"], e); rel[f] = None
        done[c["id"]] = rel
        JUDGED.write_text(json.dumps(done))
    print(len(done), "judged", llm.usage_summary())


# ---------------- scoring (offline)
def _bm25(docs):
    from rank_bm25 import BM25Okapi
    tok = lambda s: [w for w in __import__("re").findall(r"[a-z]+", s.lower()) if len(w) > 2]
    m = BM25Okapi([tok(d) for d in docs]); return lambda q: np.array(m.get_scores(tok(q)))


def _tfidf(docs):
    from sklearn.feature_extraction.text import TfidfVectorizer
    v = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, stop_words=None).fit(docs); M = v.transform(docs)
    return lambda q: np.asarray((M @ v.transform([q]).T).todense()).ravel()


def retrievers(corp: list[Unit]):
    allt, mapu = [text_all(u) for u in corp], [u for u in corp if u.branches]
    return {"bm25": (_bm25(allt), corp), "tfidf": (_tfidf(allt), corp), "care_map": (_tfidf([text_map(u) for u in mapu]), mapu)}


def pick_threshold(scores_correct: list[tuple[float, bool, bool]]) -> float:
    """scores_correct: (top score, answerable, top1 correct). Choose tau maximising accuracy of answer/abstain decisions."""
    best, tau = -1, 0.0
    for t in sorted({s for s, _, _ in scores_correct}) + [1e9]:
        acc = np.mean([(s >= t and ok) or (s < t and not ans) for s, ans, ok in scores_correct])
        if acc > best: best, tau = acc, t
    return tau


def run(rag: bool = True):
    units = eligible(load_units()); by_id = {u.unit_id: u for u in units}
    cases = json.loads(CASES.read_text()); judged = json.loads(JUDGED.read_text())
    rows = {"bm25": [], "tfidf": [], "care_map": [], "care_map+scope": [], "rag_llm": []}
    for c in cases:
        folds = [c["fold"]] if c["fold"] != "ALL" else list(FOLDS)
        for f in folds:
            rel = judged.get(c["id"], {}).get(f)
            if rel is None: continue
            rel = [r for r in rel if r in by_id and SESSION_FOLD[by_id[r].session] != f]
            corp = corpus_for(f, units); rts = retrievers(corp)
            esc = c["kind"] == "escalate"; sc = scope.classify(c["query"])
            for name, (fn, docs) in rts.items():
                s = fn(c["query"]); order = np.argsort(-s)[:3]; top = [docs[i].unit_id for i in order]
                answerable = bool(rel) and not esc
                rank = next((i + 1 for i, u in enumerate(top) if u in rel), None)
                rec = {"id": c["id"], "kind": c["kind"], "fold": f, "session": c["session"] or f, "answerable": answerable, "esc": esc, "score": float(s[order[0]]) if len(s) else 0.0,
                       "top1_ok": bool(top and top[0] in rel), "rank": rank, "scope_escalate": sc["escalate"]}
                rows[name].append(rec)
                if name == "care_map": rows["care_map+scope"].append(rec)
    res = {"note": "LLM-adjudicated labels (not clinician-reviewed); small corpus; indicative, not conclusive.", "folds": FOLDS, "n_queries": len(cases), "systems": {}}
    for name in ["bm25", "tfidf", "care_map", "care_map+scope"]:
        res["systems"][name] = score_system(rows[name], with_scope=name.endswith("+scope"))
    res["usage"] = llm.usage_summary()
    RESULTS.write_text(json.dumps(res, indent=1)); print(json.dumps(res["systems"], indent=1))


def decide(rows, with_scope):
    """Out-of-fold thresholds: tau for fold k is tuned on the other folds only."""
    out = []
    for r in rows:
        others = [(x["score"], x["answerable"], x["top1_ok"]) for x in rows if x["fold"] != r["fold"] and not x["esc"]]
        tau = pick_threshold(others) if others else 0.0
        answered = r["score"] >= tau
        escalated = with_scope and r["scope_escalate"]
        out.append({**r, "answered": answered and not escalated, "escalated": bool(escalated)})
    return out


def score_system(rows, with_scope=False, boot=300, seed=0):
    d = decide(rows, with_scope)
    def metrics(ds):
        ans = [x for x in ds if x["answerable"]]; non = [x for x in ds if not x["answerable"] and not x["esc"]]; esc = [x for x in ds if x["esc"]]
        a_rec3 = np.mean([x["rank"] is not None for x in ans]) if ans else float("nan")
        mrr = np.mean([1 / x["rank"] if x["rank"] else 0 for x in ans]) if ans else float("nan")
        answered = [x for x in ds if x["answered"] and not x["esc"]]
        sel = np.mean([x["top1_ok"] for x in answered]) if answered else float("nan")
        cov = len(answered) / max(1, len([x for x in ds if not x["esc"]]))
        abst_ok = np.mean([not x["answered"] for x in non]) if non else float("nan")
        esc_rec = np.mean([x["escalated"] or not x["answered"] for x in esc]) if esc else float("nan")
        esc_strict = np.mean([x["escalated"] for x in esc]) if esc else float("nan")
        return {"recall@3": a_rec3, "mrr": mrr, "selective_acc_top1": sel, "coverage": cov, "correct_abstention_rate": abst_ok,
                "escalation_recall_flagged": esc_strict, "escalation_recall_abstain_or_flag": esc_rec,
                "n_answerable": len(ans), "n_out_of_knowledge": len(non), "n_escalate": len(esc)}
    base = metrics(d)
    rng = random.Random(seed); sess = sorted({x["session"] for x in d}); ci = {}
    draws = []
    for _ in range(boot):
        pick = [rng.choice(sess) for _ in sess]; sub = [x for s in pick for x in d if x["session"] == s]
        draws.append(metrics(sub))
    for k in base:
        if k.startswith("n_"): continue
        v = [m[k] for m in draws if not np.isnan(m[k])]
        ci[k] = [round(float(np.percentile(v, 2.5)), 3), round(float(np.percentile(v, 97.5)), 3)] if v else None
    return {**{k: (round(float(v), 3) if not isinstance(v, int) else v) for k, v in base.items()}, "ci95_by_session": ci}


if __name__ == "__main__":
    {"gen": gen, "judge": judge, "run": run}[sys.argv[1] if len(sys.argv) > 1 else "run"]()
