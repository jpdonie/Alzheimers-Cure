"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, explain, type Form, type Gate, type Question, type SandboxEvent } from "@/lib/engine";
import { CareRecordSandbox, EMPTY } from "@/components/CareRecordSandbox";
import { PauseGate, QuestionCaption } from "@/components/QuestionPanel";
import { useVoiceAgent } from "@/lib/voice";

const DEBOUNCED = new Set(["observation", "occurrences_today"]);
const NO_RETRY = ["fresh", "already asked", "no uncertain slot", "unknown event"];

export default function Capture() {
  const [form, setForm] = useState<Form>(EMPTY);
  const [events, setEvents] = useState<SandboxEvent[]>([]);
  const [question, setQuestion] = useState<Question | null>(null);
  const [asked, setAsked] = useState<Question[]>([]);
  const [gate, setGate] = useState<Gate>({});
  const [scenario, setScenario] = useState<{ title: string; resident: string; facts: string[]; note: string } | null>(null);
  const [offRecord, setOffRecord] = useState(false);
  const [typed, setTyped] = useState("");
  const [note, setNote] = useState<string>("");
  const [transition, setTransition] = useState<string>("");
  const [sharing, setSharing] = useState(false);
  const [clinical, setClinical] = useState("");

  const eventsRef = useRef<SandboxEvent[]>([]);
  const qRef = useRef<Question | null>(null);
  const triedRef = useRef(new Set<string>());
  const lastActivity = useRef(0), lastEventAt = useRef(0), lastTry = useRef(0);
  const buf = useRef(""); const bufTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const video = useRef<HTMLVideoElement | null>(null);
  const offRef = useRef(false);

  const submitAnswer = useCallback(async (text: string) => {
    const q = qRef.current; if (!q || !text.trim()) return;
    qRef.current = null; setQuestion(null); buf.current = ""; setTyped("");
    const r = await api.answer(q.id, text.trim());
    setTransition(r.dont_know ? `${q.slot}: left unresolved ("I don't know" accepted)` : `${q.slot}: ${r.transition.before} → ${r.transition.after}`);
  }, []);

  const voice = useVoiceAgent({ role: "interviewer", onUserMessage: (t) => {
    if (!qRef.current || offRef.current) return;   // nothing is collected while off the record
    buf.current += " " + t; clearTimeout(bufTimer.current);
    bufTimer.current = setTimeout(() => submitAnswer(buf.current), 3000);
  } });

  useEffect(() => { api.session("capture").then((s) => setScenario(s.capture_scenario)).catch((e) => setNote(explain(e))); }, []);

  const grabFrame = useCallback(async (eventId: string) => {
    const v = video.current, el = document.getElementById("sandbox");
    if (!v || !el || !v.videoWidth) return;
    const k = v.videoWidth / window.innerWidth, r = el.getBoundingClientRect();
    const w = Math.min(640, r.width * k), c = document.createElement("canvas");
    c.width = w; c.height = (r.height * k) * (w / (r.width * k));
    c.getContext("2d")?.drawImage(v, r.left * k, r.top * k, r.width * k, r.height * k, 0, 0, c.width, c.height); // crop to the sandbox only
    await api.frame(eventId, c.toDataURL("image/jpeg", 0.6));
  }, []);

  const emit = useCallback(async (field: string, value: unknown, next: Form, delta?: unknown) => {
    if (offRef.current) return;
    const res = await api.event({ field, value, delta, form: next }).catch(() => null);   // rejected (409) if recording is off
    if (!res) return;
    const { event } = res;
    if (res.scope) setClinical(res.scope.escalate ? res.scope.reason : "");
    eventsRef.current = [...eventsRef.current, event]; setEvents(eventsRef.current);
    lastEventAt.current = Date.now(); voice.context(event.text);
    setTimeout(() => grabFrame(event.id), 200);
  }, [grabFrame, voice]);

  const pending = useRef<Record<string, { value: unknown; next: Form }>>({});
  const flush = useCallback(async (except?: string) => {
    for (const [f, p] of Object.entries(pending.current)) {   // keep event order faithful to what happened on screen
      if (f === except) continue;
      clearTimeout(timers.current[f]); delete pending.current[f]; await emit(f, p.value, p.next);
    }
  }, [emit]);
  const onChange = (next: Form, field: string, delta?: { added?: string; removed?: string }) => {
    setForm(next); lastActivity.current = Date.now(); lastEventAt.current = Date.now();
    const value = (next as unknown as Record<string, unknown>)[field];
    if (DEBOUNCED.has(field)) {
      pending.current[field] = { value, next }; clearTimeout(timers.current[field]);
      timers.current[field] = setTimeout(() => flush(), 1200);
    } else flush(field).then(() => emit(field, value, next, delta));
  };

  useEffect(() => {
    const t = setInterval(async () => {
      const now = Date.now();
      const sig = { hands_still: now - lastActivity.current > 2500, screen_stable: now - lastEventAt.current > 1500, voice_silent: voice.connected ? voice.silentFor() > 1500 : true };
      setGate((g) => ({ ...g, ...sig }));
      const latest = eventsRef.current.at(-1);   // only the newest event may trigger a question
      if (!latest || offRef.current || qRef.current || triedRef.current.has(latest.id)) return;
      if (!Object.values(sig).every(Boolean) || now - lastTry.current < 2000) return;
      lastTry.current = now;
      const res = await api.question(latest.id, sig).catch(() => null); if (!res) return;
      setGate(res.gate);
      if (res.question) { triedRef.current.add(latest.id); qRef.current = res.question; setQuestion(res.question); setAsked((a) => [...a, res.question!]); setTransition(""); voice.tell("ASK", res.question.text); }
      else if (NO_RETRY.some((x) => res.reason.includes(x))) triedRef.current.add(latest.id);
    }, 500);
    return () => clearInterval(t);
  }, [voice]);

  const share = async () => {
    try {
      const s = await navigator.mediaDevices.getDisplayMedia({ video: { displaySurface: "browser" }, preferCurrentTab: true } as DisplayMediaStreamOptions);
      const v = document.createElement("video"); v.srcObject = s; v.muted = true; await v.play(); video.current = v; setSharing(true);
      s.getVideoTracks()[0].onended = () => { video.current = null; setSharing(false); };
    } catch { setNote("Screen share declined: continuing with DOM events only (degraded mode)."); }
  };

  const toggleOff = async () => {
    const next = !offRef.current;
    offRef.current = next; setOffRecord(next);            // client stops first, then the server refuses late writes
    if (next) { voice.stop(); qRef.current = null; setQuestion(null); buf.current = ""; }
    await api.recording(!next).catch(() => {});
    setNote(next ? "Off the record: collection stopped, voice disconnected. Restart voice to continue." : "Recording again.");
  };
  const deleteLastMinute = async () => {
    const last = eventsRef.current.at(-1)?.ts ?? 0; const r = await api.offRecord(Math.max(0, last - 60));
    eventsRef.current = []; setEvents([]); qRef.current = null; setQuestion(null);
    setNote(`Deleted locally: ${r.events} events, ${r.frames} frames, ${r.answers} answers. ${r.disclosure}`);
  };

  const guardrailQs = asked.filter((q) => q.type === "guardrail" || q.type === "escalation").length;
  const state = voice.speaking ? "asking" : question ? "waiting" : "quiet";

  return (
    <div className="grid gap-4 lg:grid-cols-5">
      <section className="space-y-3 lg:col-span-3">
        {scenario && <div className="card bg-sage"><b>Your task (fake data): {scenario.title}.</b> {scenario.note}</div>}
        <CareRecordSandbox resident={scenario?.resident ?? "R-204"} form={form} facts={scenario?.facts} onChange={onChange} onActivity={() => { lastActivity.current = Date.now(); }}
          onSave={() => flush().then(() => emit("save", true, form))} />
        <div className="card">
          <h3 className="font-semibold mb-2">Screen events {sharing ? "· frames cropped to this form" : "· DOM events only"}</h3>
          <ol className="max-h-40 space-y-1 overflow-auto text-sm">
            {events.map((e) => <li key={e.id}><span className="chip">{e.ts.toFixed(0)}s</span> {e.text}</li>)}
          </ol>
        </div>
      </section>
      <aside className="space-y-3 lg:col-span-2">
        <div className="card space-y-3">
          <div className="flex flex-wrap gap-2">
            <button className="btn btn-primary" onClick={voice.start} disabled={voice.connected}>{voice.connected ? "Voice connected" : "Start voice"}</button>
            <button className="btn btn-ghost" onClick={share} disabled={sharing}>{sharing ? "Sharing this tab" : "Share screen"}</button>
            <button className={`btn ${offRecord ? "btn-primary bg-coral border-coral" : "btn-ghost"}`} onClick={toggleOff}>{offRecord ? "Off the record: ON" : "Off the record"}</button>
            <button className="btn btn-ghost" onClick={deleteLastMinute}>Delete last minute</button>
          </div>
          {clinical && <p className="rounded-lg border border-coral bg-coral/10 p-2 text-sm text-coral">Clinical concern: {clinical}</p>}
          {voice.error && <p className="text-sm text-coral">Voice unavailable ({voice.error}). Captions and typed answers still work.</p>}
          <PauseGate gate={gate} />
          <QuestionCaption q={question} state={state} />
          {question && (
            <div className="space-y-2">
              <textarea className="w-full rounded-lg border border-line p-2" rows={2} placeholder="Answer by voice, or type here" value={typed} onChange={(e) => setTyped(e.target.value)} />
              <div className="flex gap-2">
                <button className="btn btn-primary" onClick={() => submitAnswer(typed)}>Send answer</button>
                <button className="btn btn-ghost" onClick={() => submitAnswer("I don't know")}>I don&apos;t know</button>
              </div>
            </div>)}
          {transition && <p className="chip bg-sage">Learned: {transition}</p>}
          {note && <p className="text-sm">{note}</p>}
        </div>
        <div className="card text-sm">
          <b>Questions asked: {asked.length}</b> (brief needs ≥ 3, with ≥ 1 guardrail: {guardrailQs}). Budget 5 per 10 minutes.
          <ul className="mt-1 list-disc pl-5">{asked.map((q) => <li key={q.id}>{q.type}: {q.text}</li>)}</ul>
        </div>
        <Link href="/debrief" className="btn btn-primary block text-center">Task finished → Debrief</Link>
      </aside>
    </div>
  );
}
