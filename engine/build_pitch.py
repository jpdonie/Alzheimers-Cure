"""Pitch-only data build (extensions): evaluation numbers, DP simulator sweep, a scripted drift vignette and learner statistics
written to web/public/pitch-data.json for the /moonshot page. The live app never imports this module."""
import json
from pathlib import Path

from . import drift, federated
from .session import Session

ROOT = Path(__file__).resolve().parent.parent
OK = {"voice_silent": True, "hands_still": True, "screen_stable": True}


def drift_vignette() -> dict:
    """Scripted: a learned boundary (3+ refusals escalate) meets an expert who stops at 2, and a save that contradicts a guardrail."""
    import os
    os.environ.setdefault("APPRENTICE_COOLDOWN", "0"); os.environ["APPRENTICE_OFFLINE"] = "1"
    s = Session("capture", drift=drift)
    out = s.add_event({"field": "save", "form": {"incident_type": "refusal_of_care", "checks": [], "occurrences_today": 1, "escalate_to": "none", "intervention": "no_action"}})
    q = out["drift_question"]
    steps = [{"event": "Expert saves a refusal note with no pain check and no escalation", "apprentice": q["text"] if q else ""}]
    if q:
        s.answer(q["id"], "This resident has a documented chronic pain plan; the nurse already owns the pain check, so I log and flag it instead.")
    steps.append({"event": "Expert explains why", "apprentice": "Rule kept, boundary versioned as an exception (never overwritten); disposition recorded: " + (s.drift_log[0]["disposition"] if s.drift_log else "")})
    r3 = s.rule("R3-repeat-escalate")
    upd = drift.boundary_update(r3, "occurrences_today", 2, "For me it is two refusals, not three.", s.now())
    steps.append({"event": "Expert says escalation starts at two refusals, not three", "apprentice": f"Boundary on R3 changed {upd['old']} -> {upd['new']}, version {upd['v']}, with the expert's quote as provenance" if upd else ""})
    return {"steps": steps}


def build():
    ev = json.loads((ROOT / "data" / "eval_results.json").read_text()) if (ROOT / "data" / "eval_results.json").exists() else {}
    lr = json.loads((ROOT / "data" / "learner_report.json").read_text()) if (ROOT / "data" / "learner_report.json").exists() else {}
    data = {"eval": {k: ev.get("systems", {}).get(k) for k in ("bm25", "tfidf", "tfidf+scope", "care_map", "care_map+scope")}, "eval_n": ev.get("n_queries"),
            "dp": federated.sweep(), "drift": drift_vignette(),
            "learner": {k: lr.get(k) for k in ("merged_cards", "by_kind", "verbatim_verified", "with_guardrails", "with_exceptions", "corroborated_2plus_sessions", "cbt_all_three", "safety_critical")}}
    out = ROOT / "web" / "public" / "pitch-data.json"
    out.parent.mkdir(exist_ok=True); out.write_text(json.dumps(data, indent=1)); print("wrote", out)


if __name__ == "__main__":
    build()
