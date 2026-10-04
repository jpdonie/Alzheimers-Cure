"""FastAPI surface for the web app. Run: uvicorn engine.api:app --port 8000"""
import contextvars, copy, json, os, threading
from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path
import base64
from fastapi import FastAPI, HTTPException, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from . import export as exporter, graph as care_graph, learned, llm, scope
from .session import Conflict, Session

app = FastAPI(title="Apprentice engine")
# Browser origins allowed to call the engine. Production sets APPRENTICE_ALLOWED_ORIGINS="https://your-app.vercel.app" (comma separated).
ALLOWED = [o.strip() for o in os.getenv("APPRENTICE_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()]
# Optional pattern for hosted preview/production URLs of OUR Vercel project(s); a bare "*.vercel.app" would let any site spend our API credits.
ORIGIN_REGEX = os.getenv("APPRENTICE_ALLOWED_ORIGIN_REGEX") or None
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED, allow_origin_regex=ORIGIN_REGEX, allow_methods=["*"], allow_headers=["*"])
SESSIONS: "OrderedDict[str, Session]" = OrderedDict()   # one Session per browser (X-Session-Id), oldest evicted
CURRENT = contextvars.ContextVar("sid", default="default")
MAX_SESSIONS = 20
REGISTRY = threading.Lock()   # guards SESSIONS only; each Session's own lock guards its state. Order: REGISTRY, then session.lock.


@app.middleware("http")
async def session_id(request, call_next):
    CURRENT.set((request.headers.get("x-session-id") or request.query_params.get("sid") or "default")[:64])
    return await call_next(request)


@app.exception_handler(Conflict)
async def conflict(_, exc: Conflict):
    return JSONResponse({"detail": str(exc)}, status_code=409)
DATA = Path(__file__).resolve().parent.parent / "data"


def S() -> Session:
    sid = CURRENT.get()
    with REGISTRY:
        if sid not in SESSIONS:
            SESSIONS[sid] = Session("capture")
            while len(SESSIONS) > MAX_SESSIONS: SESSIONS.popitem(last=False)[1].retire()
        SESSIONS.move_to_end(sid)
        return SESSIONS[sid]


@contextmanager
def locked():
    """This browser's session, held for one short critical section. Never call a model inside it."""
    s = S()
    with s.lock:
        yield s


class NewSession(BaseModel): mode: Literal["capture", "teach"] = "capture"
Interp = Literal["none", "behavioural_agitation", "physical_cause_suspected", "environmental", "unmet_basic_need", "sundowning", "boredom", "unknown"]
Check = Literal["pain", "footwear_skin", "hunger_thirst", "hearing_vision_aids", "noise_environment", "toileting", "signage_routine"]
Interv = Literal["no_action", "retry_later_same_carer", "swap_carer_or_call_psychologist", "reassure_and_note", "give_prn_medication", "request_antipsychotic", "adjust_diet", "integration_plan_review", "prompted_toileting", "restore_signage", "add_activities"]
Escal = Literal["none", "nurse", "psychologist", "team_meeting", "coordinating_physician"]


class FormIn(BaseModel):
    """The sandbox form, validated at the boundary (the guard evaluates this exact shape)."""
    model_config = ConfigDict(extra="forbid")
    incident_type: Literal["refusal_of_care", "exit_seeking", "wandering", "medication_request", "other"] = "refusal_of_care"
    observation: str = Field("", max_length=1000)
    interpretation: Interp = "none"
    checks: list[Check] = Field(default_factory=list, max_length=7)
    occurrences_today: int = Field(1, ge=0, le=50)
    months_in_residence: int = Field(0, ge=0, le=600)
    pattern: Literal["", "new", "habitual", "unsure"] = ""
    intervention: Interv = "no_action"
    escalate_to: Escal = "none"


class Ev(BaseModel):
    field: Literal["incident_type", "observation", "interpretation", "checks", "occurrences_today", "months_in_residence", "pattern", "intervention", "escalate_to", "save"]
    value: object = None; delta: dict | None = None; form: FormIn | None = None
class Frame(BaseModel): event_id: str = Field(max_length=40); data_url: str = Field(max_length=2_000_000, pattern=r"^data:image/(jpeg|png);base64,")
class Ask(BaseModel): event_id: str; signals: dict
class Ans(BaseModel): question_id: str = Field(max_length=40); text: str = Field(min_length=1, max_length=2000); ts: float | None = None
class Conf(BaseModel): rule_id: str = Field(max_length=60); ok: bool; correction: str | None = Field(default=None, max_length=1000)
class Off(BaseModel): since_ts: float = Field(ge=0)
class Pred(BaseModel): case_id: str = Field(max_length=10); option: Literal["a", "b", "c", "d"]
class Save(BaseModel): case_id: str = Field(max_length=10); form: FormIn
class Rec(BaseModel): on: bool
class Rev(BaseModel): rule_id: str = Field(max_length=60); decision: Literal["confirm", "reject", "reset"]; note: str = Field("", max_length=600)


@app.get("/health")
def health():
    with locked() as s: out = {"ok": True, "session": s.id, "degraded": s.degraded}
    return out | {"usage": llm.usage_summary()}

@app.post("/session")
def new(b: NewSession):
    s, sid = Session(b.mode), CURRENT.get()
    with REGISTRY:
        old = SESSIONS.get(sid)
        if old:
            with old.lock:
                if b.mode == "teach":   # keep what the apprentice learned in capture
                    s.rules, s.teachback, s.frames, s.drift_log = copy.deepcopy(old.rules), dict(old.teachback), dict(old.frames), copy.deepcopy(old.drift_log)
                    s.events, s.questions, s.answers = copy.deepcopy(old.events), copy.deepcopy(old.questions), copy.deepcopy(old.answers)
                old.retire()
        if b.mode == "teach": s.freeze()
        SESSIONS[sid] = s; SESSIONS.move_to_end(sid)
        while len(SESSIONS) > MAX_SESSIONS: SESSIONS.popitem(last=False)[1].retire()
    return {"id": s.id, "mode": s.mode, "capture_scenario": s.cases["capture_scenario"]}

@app.get("/cases")
def cases():
    with locked() as s: return jsonable_encoder({"capture": s.cases["capture_scenario"], "teach": [{"id": c["id"], "title": c["title"], "resident": c["resident"]} for c in s.cases["teach_cases"]]})

@app.post("/events")
def events(e: Ev):
    with locked() as s: r = jsonable_encoder(s.add_event(e.model_dump()))
    if e.field == "observation":   # fail-closed clinical language check, visible to the expert while they type
        r["scope"] = scope.classify(str(e.value or ""))
    return r

@app.post("/recording")
def recording(r: Rec):
    with locked() as s: return jsonable_encoder(s.set_recording(r.on))

@app.post("/frames")
def frames(f: Frame): return {"ok": True, "vision": S().add_frame(f.event_id, f.data_url)}   # locks itself; vision runs unlocked

@app.get("/frame/{event_id}")
def frame(event_id: str):
    with locked() as s: d = s.frames.get(event_id)
    if not d: raise HTTPException(404, "no frame")
    head, _, b64 = d.partition(",")
    return Response(base64.b64decode(b64), media_type="image/jpeg")

@app.post("/question")
def question(a: Ask):
    with locked() as s: return jsonable_encoder(s.propose_question(a.event_id, a.signals))

@app.post("/answer")
def answer(a: Ans):
    try: return S().answer(a.question_id, a.text, a.ts)   # locks itself; extraction runs unlocked
    except StopIteration: raise HTTPException(404, "unknown question")

@app.post("/debrief/start")
def debrief_start():
    with locked() as s: return jsonable_encoder(s.debrief_start())
@app.get("/debrief/status")
def debrief_status():
    with locked() as s: return jsonable_encoder(s.debrief_status())
@app.get("/debrief/teachback")
def teachback(): return S().teachback_text()   # locks itself; the model runs unlocked
@app.post("/debrief/confirm")
def confirm(c: Conf):
    with locked() as s: return jsonable_encoder(s.confirm(c.rule_id, c.ok, c.correction))

@app.get("/workmap")
def workmap():
    with locked() as s: return jsonable_encoder(s.workmap())
@app.post("/off-record")
def off(o: Off):
    with locked() as s: return jsonable_encoder(s.off_record(o.since_ts))

@app.post("/teach/open")
def t_open(b: dict):
    try:
        with locked() as s: return jsonable_encoder(s.teach_open(b["case_id"]))
    except (StopIteration, KeyError): raise HTTPException(404, "unknown case")
@app.post("/teach/predict")
def t_pred(p: Pred):
    try:
        with locked() as s: return jsonable_encoder(s.teach_predict(p.case_id, p.option))
    except StopIteration: raise HTTPException(404, "unknown case")
@app.post("/teach/check-save")
def t_save(p: Save):
    try:
        with locked() as s: return jsonable_encoder(s.teach_check_save(p.case_id, p.form.model_dump()))
    except StopIteration: raise HTTPException(404, "unknown case")
@app.get("/mastery")
def mastery():
    with locked() as s: return jsonable_encoder({"rows": s.mastery.summary()})

@app.post("/teach/brief")
def t_brief(b: dict):
    """Expert-reasoning brief for the tutor agent (pushed as a contextual update)."""
    with locked() as s:
        c = next(x for x in s.cases["teach_cases"] if x["id"] == b["case_id"])
        exs = jsonable_encoder([s._explain(s.rule(rid)) for rid in c["rule_ids"]])
    lines = []
    for rid, ex in zip(c["rule_ids"], exs):
        quotes = " | ".join(f"\"{w['quote']}\"" for w in ex["expert_words"])
        notes = " | ".join(d["summary"] for d in ex["dataset_summaries"])
        lines.append(f"Rule {rid}: {ex['title']}. Verbatim expert words: {quotes or 'none'}." + (f" Dataset summary (not a quotation): {notes}." if notes else ""))
    return {"brief": "\n".join(lines)}

@app.post("/review")
def review(r: Rev):
    with locked() as s: return jsonable_encoder(s.review(r.rule_id, r.decision, r.note))

@app.get("/graph")
def graph():
    with locked() as s: return jsonable_encoder(care_graph.build(s))

@app.get("/export")
def export_guardrails():
    with locked() as s: body = exporter.build(s.rules, s.teachback, s.map_version())
    return Response(body, media_type="text/markdown; charset=utf-8",
                    headers={"content-disposition": 'attachment; filename="apprentice-guardrails.md"'})

@app.get("/learned")
def learned_map():
    """Everything the apprentice learned from all interview units, with each card's review state."""
    d = learned.load()
    with locked() as s: revs = copy.deepcopy(s.reviews)
    rep_path = DATA / "learner_report.json"
    def rv(c):   # a review counts only if it still points at the same card title
        r = revs.get(c["id"], {})
        return r if r and (not r.get("title") or r["title"] == c["title"]) else {}
    return {"cards": [{**c, "review": rv(c).get("decision", ""), "review_note": rv(c).get("note", ""),
                       "enforced": rv(c).get("decision") == "confirm" and bool(c.get("proposed_predicate"))} for c in d["cards"]],
            "agenda": d.get("agenda", []), "report": json.loads(rep_path.read_text()) if rep_path.exists() else {}}

@app.get("/rules")
def rules():
    with locked() as s: return jsonable_encoder({"rules": s.rules})
@app.get("/usage")
def usage(): return llm.usage_summary()
if "dp" in os.getenv("APPRENTICE_EXTENSIONS", ""):   # deferred extension: never part of the live path
    from . import federated

    @app.get("/dp-sweep")
    def dp(): return {"note": "Simulation only; org = privacy unit", "sweep": federated.sweep()}
@app.get("/eval")
def ev():
    p = DATA / "eval_results.json"
    return json.loads(p.read_text()) if p.exists() else {"error": "run python -m engine.eval_heldout"}
