"""FastAPI surface for the web app. Run: uvicorn engine.api:app --port 8000"""
import json
from pathlib import Path
import base64
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import llm, federated
from .session import Session

app = FastAPI(title="Apprentice engine")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], allow_methods=["*"], allow_headers=["*"])
STATE: dict = {"s": Session("capture")}
DATA = Path(__file__).resolve().parent.parent / "data"


def S() -> Session: return STATE["s"]


class NewSession(BaseModel): mode: str = "capture"
class Ev(BaseModel):
    field: str; value: object = None; delta: dict | None = None; form: dict | None = None; ts: float | None = None
class Frame(BaseModel): event_id: str; data_url: str
class Ask(BaseModel): event_id: str; signals: dict
class Ans(BaseModel): question_id: str; text: str; ts: float | None = None
class Conf(BaseModel): rule_id: str; ok: bool; correction: str | None = None
class Off(BaseModel): since_ts: float
class Pred(BaseModel): case_id: str; option: str
class Save(BaseModel): case_id: str; form: dict


@app.get("/health")
def health(): return {"ok": True, "session": S().id, "degraded": S().degraded, "usage": llm.usage_summary()}

@app.post("/session")
def new(b: NewSession):
    if b.mode == "teach":   # keep what the apprentice learned in capture
        old = STATE["s"]; s = Session("teach")
        s.rules, s.teachback, s.frames, s.drift_log = old.rules, old.teachback, old.frames, old.drift_log
        s.events, s.questions, s.answers = old.events, old.questions, old.answers
        STATE["s"] = s
    else:
        STATE["s"] = Session(b.mode)
    return {"id": S().id, "mode": S().mode, "capture_scenario": S().cases["capture_scenario"]}

@app.get("/cases")
def cases(): return {"capture": S().cases["capture_scenario"], "teach": [{"id": c["id"], "title": c["title"], "resident": c["resident"]} for c in S().cases["teach_cases"]]}

@app.post("/events")
def events(e: Ev): return S().add_event(e.model_dump())

@app.post("/frames")
def frames(f: Frame): S().add_frame(f.event_id, f.data_url); return {"ok": True}

@app.get("/frame/{event_id}")
def frame(event_id: str):
    d = S().frames.get(event_id)
    if not d: raise HTTPException(404, "no frame")
    head, _, b64 = d.partition(",")
    return Response(base64.b64decode(b64), media_type="image/jpeg")

@app.post("/question")
def question(a: Ask): return S().propose_question(a.event_id, a.signals)

@app.post("/answer")
def answer(a: Ans):
    try: return S().answer(a.question_id, a.text, a.ts)
    except StopIteration: raise HTTPException(404, "unknown question")

@app.post("/debrief/start")
def debrief_start(): return S().debrief_start()
@app.get("/debrief/status")
def debrief_status(): return S().debrief_status()
@app.get("/debrief/teachback")
def teachback(): return S().teachback_text()
@app.post("/debrief/confirm")
def confirm(c: Conf): return S().confirm(c.rule_id, c.ok, c.correction)

@app.get("/workmap")
def workmap(): return S().workmap()
@app.post("/off-record")
def off(o: Off): return S().off_record(o.since_ts)

@app.post("/teach/open")
def t_open(b: dict): return S().teach_open(b["case_id"])
@app.post("/teach/predict")
def t_pred(p: Pred): return S().teach_predict(p.case_id, p.option)
@app.post("/teach/check-save")
def t_save(p: Save): return S().teach_check_save(p.case_id, p.form)
@app.get("/mastery")
def mastery(): return {"rows": S().mastery.summary()}

@app.post("/teach/brief")
def t_brief(b: dict):
    """Expert-reasoning brief for the tutor agent (pushed as a contextual update)."""
    c = next(x for x in S().cases["teach_cases"] if x["id"] == b["case_id"])
    lines = []
    for rid in c["rule_ids"]:
        ex = S()._explain(S().rule(rid))
        lines.append(f"Rule {rid}: {ex['title']}. Expert words: " + " | ".join(w["quote"] for w in ex["expert_words"]))
    return {"brief": "\n".join(lines)}

@app.get("/rules")
def rules(): return {"rules": S().rules}
@app.get("/usage")
def usage(): return llm.usage_summary()
@app.get("/dp-sweep")
def dp(): return {"note": "Simulation only; org = privacy unit", "sweep": federated.sweep()}
@app.get("/eval")
def ev():
    p = DATA / "eval_results.json"
    return json.loads(p.read_text()) if p.exists() else {"error": "run python -m engine.eval_heldout"}
