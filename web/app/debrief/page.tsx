"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, explain, type Question } from "@/lib/engine";
import { useVoiceAgent } from "@/lib/voice";

type Status = Awaited<ReturnType<typeof api.debriefStatus>>;

export default function Debrief() {
  const [qs, setQs] = useState<Question[]>([]);
  const [idx, setIdx] = useState(0);
  const [typed, setTyped] = useState("");
  const [log, setLog] = useState<string[]>([]);
  const [tb, setTb] = useState<{ text: string; steps: { step_id: string; rule_id: string; summary: string }[] } | null>(null);
  const [verdict, setVerdict] = useState<Record<string, string>>({});
  const [fix, setFix] = useState<Record<string, string>>({});
  const [status, setStatus] = useState<Status | null>(null);
  const [err, setErr] = useState("");
  const buf = useRef(""); const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const cur = qs[idx]; const curRef = useRef<Question | undefined>(undefined);
  useEffect(() => { curRef.current = cur; }, [cur]);

  const refresh = useCallback(() => api.debriefStatus().then(setStatus).catch(() => {}), []);
  const submit = useCallback(async (text: string) => {
    const q = curRef.current; if (!q || !text.trim()) return;
    buf.current = ""; setTyped("");
    const r = await api.answer(q.id, text.trim());
    setLog((l) => [...l, `${q.slot}: ${r.dont_know ? "left unresolved" : `${r.transition.before} → ${r.transition.after}`}`]);
    setIdx((i) => i + 1); refresh();
  }, [refresh]);
  const voice = useVoiceAgent({ role: "interviewer", onUserMessage: (t) => { buf.current += " " + t; clearTimeout(timer.current); timer.current = setTimeout(() => submit(buf.current), 3000); } });

  useEffect(() => { api.debriefStart().then((d) => { setQs(d.questions); refresh(); }).catch((e) => setErr(explain(e))); }, [refresh]);
  useEffect(() => { if (cur) voice.tell("ASK", cur.text); }, [cur?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const startTeachBack = async () => { const t = await api.teachback(); setTb(t); voice.tell("TEACHBACK", t.text); };
  const decide = async (rule_id: string, ok: boolean) => {
    const r = await api.confirm(rule_id, ok, ok ? undefined : fix[rule_id]);
    setVerdict((v) => ({ ...v, [rule_id]: r.teach_back })); refresh();
  };

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="space-y-3">
        <div className="card">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold">Debrief: what I am still unsure about</h2>
            <button className="btn btn-primary" onClick={voice.start} disabled={voice.connected}>{voice.connected ? "Voice connected" : "Start voice"}</button>
          </div>
          {err && <p className="text-coral">{err} <Link href="/capture" className="underline">Go to Capture</Link></p>}
          <p className="text-sm">Ranked by risk and missing knowledge. These were not answered during the task.</p>
          <ol className="mt-2 space-y-2">
            {qs.map((q, i) => (
              <li key={q.id} className={`rounded-lg border p-2 ${i === idx ? "border-amber bg-amber/10" : "border-line"} ${i < idx ? "opacity-60" : ""}`}>
                <div className="flex flex-wrap gap-2"><span className="chip">{q.type === "unseen" ? "case I have not seen" : q.slot}</span><span className="chip">{q.rule_id}</span><span className="chip">score {q.score}</span></div>
                <p className="mt-1">{q.text}</p>
              </li>))}
          </ol>
          {cur && (
            <div className="mt-3 space-y-2">
              <textarea className="w-full rounded-lg border border-line p-2" rows={2} placeholder="Answer by voice, or type" value={typed} onChange={(e) => setTyped(e.target.value)} />
              <div className="flex gap-2">
                <button className="btn btn-primary" onClick={() => submit(typed)}>Send answer</button>
                <button className="btn btn-ghost" onClick={() => submit("I don't know")}>I don&apos;t know</button>
              </div>
            </div>)}
          <ul className="mt-2 text-sm">{log.map((l, i) => <li key={i} className="chip bg-sage mr-1">{l}</li>)}</ul>
        </div>
      </section>
      <section className="space-y-3">
        <div className="card">
          <h2 className="text-lg font-bold">Teach-back</h2>
          {!tb ? <button className="btn btn-primary" onClick={startTeachBack} disabled={idx < Math.min(3, qs.length)}>Explain the process back to me</button> : (
            <div className="space-y-2">
              <p className="whitespace-pre-line text-sm">{tb.text}</p>
              {tb.steps.map((s) => (
                <div key={s.step_id} className="rounded-lg border border-line p-2">
                  <p className="text-sm">{s.summary}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    <button className="btn btn-ghost" onClick={() => decide(s.rule_id, true)}>Yes, that is it</button>
                    <input className="flex-1 rounded border border-line px-2 py-1" placeholder="Correct it: what is missing or wrong?" value={fix[s.rule_id] ?? ""} onChange={(e) => setFix((f) => ({ ...f, [s.rule_id]: e.target.value }))} />
                    <button className="btn btn-ghost" disabled={!fix[s.rule_id]} onClick={() => decide(s.rule_id, false)}>Correct it</button>
                    {verdict[s.rule_id] && <span className="chip bg-sage">{verdict[s.rule_id] === "confirmed" ? "confirmed by expert" : "correction saved as an expert exception on this rule"}</span>}
                  </div>
                </div>))}
            </div>)}
        </div>
        {status && (
          <div className="card text-sm">
            <h3 className="font-semibold">Done-ness checks</h3>
            <ul className="list-disc pl-5">
              <li>{status.needs_3_new ? "✓" : "○"} at least 3 new follow-ups answered ({status.new_followups_answered})</li>
              <li>{status.guardrails_covered ? "✓" : "○"} guardrails for touched rules stated by the expert</li>
              <li>{status.teach_back_done ? "✓" : "○"} teach-back confirmed or corrected for every step</li>
            </ul>
            <p className="mt-1 text-ink/70">{status.note} Residual gaps: {status.residual_gaps.map((g) => `${g.rule_id}/${g.slot}`).join(", ") || "none"}.</p>
          </div>)}
        <Link href="/map" className="btn btn-primary block text-center">See the Work Map →</Link>
      </section>
    </div>
  );
}
