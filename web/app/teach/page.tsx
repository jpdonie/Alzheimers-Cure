"use client";
import { useCallback, useEffect, useState } from "react";
import { api, type Block, type Form } from "@/lib/engine";
import { CareRecordSandbox, EMPTY } from "@/components/CareRecordSandbox";
import { useVoiceAgent } from "@/lib/voice";

type Case = Awaited<ReturnType<typeof api.teachOpen>>;
type Result = Awaited<ReturnType<typeof api.checkSave>>;

function Intercept({ blocks, onClose }: { blocks: Block[]; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-10 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal>
      <div className="max-h-[90vh] w-full max-w-3xl space-y-3 overflow-auto rounded-2xl border-2 border-coral bg-white p-5">
        <h3 className="text-xl font-bold text-coral">Hold on: not saved yet</h3>
        {blocks.map((b) => (
          <div key={b.rule_id} className="space-y-2 rounded-lg border border-coral/50 p-3">
            <p className="font-semibold">{b.title}</p>
            <div className="flex flex-wrap gap-2"><span className="chip border-amber bg-amber/20">guardrail {b.guardrail_id}</span><span className="chip">{b.evidence_class}</span></div>
            <p className="text-sm">{b.message}</p>
            <table className="w-full text-sm"><thead><tr className="text-left"><th>Field</th><th>Rule needs</th><th>You entered</th><th /></tr></thead>
              <tbody>{b.trace.map((t, i) => <tr key={i}><td>{t.field}</td><td>{t.op} {JSON.stringify(t.expected)}</td><td>{JSON.stringify(t.observed)}</td><td>{t.met ? "matched" : "not matched"}</td></tr>)}</tbody></table>
            <p className="font-mono text-xs">predicate: {b.text}</p>
            {b.explain.expert_words.map((w, i) => (
              <blockquote key={i} className="quote">“{w.quote}” <span className="text-xs">({w.kind === "screen" ? "expert, live" : `transcript ${w.unit_id}, verbatim`})</span></blockquote>))}
            {b.explain.dataset_summaries.map((d, i) => <p key={i} className="text-sm"><span className="chip">dataset summary, not a quotation</span> {d.summary} ({d.unit_id})</p>)}
            {b.explain.screen_moment
              ? <div><p className="text-sm font-semibold">Replay: the expert&apos;s screen moment ({b.explain.screen_moment.ts.toFixed(0)}s)</p><img src={api.frameUrl(b.explain.screen_moment.event_id)} alt="Expert screen moment" className="max-h-48 rounded border" onError={(e) => ((e.target as HTMLElement).style.display = "none")} /></div>
              : <p className="text-sm text-ink/70">No live screen moment yet for this rule: the evidence is from transcripts.</p>}
          </div>))}
        <button className="btn btn-primary" onClick={onClose}>Fix it</button>
      </div>
    </div>
  );
}

export default function Teach() {
  const [cases, setCases] = useState<{ id: string; title: string }[]>([]);
  const [caseId, setCaseId] = useState("T1");
  const [c, setC] = useState<Case | null>(null);
  const [form, setForm] = useState<Form>(EMPTY);
  const [picked, setPicked] = useState<string>("");
  const [pred, setPred] = useState<{ correct: boolean | null } | null>(null);
  const [blocks, setBlocks] = useState<Block[] | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [err, setErr] = useState("");
  const voice = useVoiceAgent({ role: "tutor" });

    const open = useCallback(async (id: string) => {
    const x = await api.teachOpen(id); setC(x); setCaseId(id); setPicked(""); setPred(null); setResult(null); setBlocks(null);
    setForm({ ...EMPTY, incident_type: "refusal_of_care", ...x.form_start } as Form);
    const b = await api.brief(id); voice.context(`The learner is on case ${x.title}. Expert reasoning for this case:\n${b.brief}`);
    voice.tell("SAY", `New case: ${x.title}. Before you touch the record, what would you do next?`);
  }, [voice]);
  useEffect(() => { api.session("teach").then(() => api.cases()).then((x) => { setCases(x.teach); return open("T1"); }).catch(() => setErr("Engine not reachable on :8000")); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const choose = async (k: string) => {
    setPicked(k);
    const r = await api.predict(caseId, k).catch(() => ({ correct: null }));   // 409: this case already has a recorded prediction
    setPred(r);
    if (r.correct === false) voice.tell("SAY", "Not quite. Hold that thought: I will show you how the expert reasons when you try to save.");
  };
  const save = async () => {
    const r = await api.checkSave(caseId, form); setResult(r);
    if (!r.saved) { setBlocks(r.blocked); voice.tell("SAY", `Wait, this is not saved yet. ${r.blocked[0]?.explain.expert_words[0]?.quote ?? ""} Why do you think the expert would stop here?`); }
    else voice.tell("SAY", "Saved. That matches how the expert reasons. Well done.");
  };

  return (
    <div className="grid gap-4 lg:grid-cols-5">
      {err && <p className="text-coral">{err}</p>}
      <section className="space-y-3 lg:col-span-3">
        {c && <CareRecordSandbox resident={c.resident} facts={c.facts} form={form} lockedType onChange={(n) => setForm(n)} onSave={() => (picked ? save() : setErr("Make your prediction first (right panel), then save."))} saveLabel="Save record" />}
      </section>
      <aside className="space-y-3 lg:col-span-2">
        <div className="card space-y-2">
          <div className="flex items-center justify-between"><h2 className="text-lg font-bold">Tutor {c && <span className="chip ml-1 text-xs" title="Same Work Map artifact the expert confirmed">map {c.map_version}</span>}</h2>
            <button className="btn btn-primary" onClick={voice.start} disabled={voice.connected}>{voice.connected ? "Voice connected" : "Start voice"}</button></div>
          <div className="flex flex-wrap gap-1">{cases.map((x) => <button key={x.id} className={`chip ${x.id === caseId ? "bg-teal text-white" : ""}`} onClick={() => open(x.id)}>{x.id}: {x.title}</button>)}</div>
          {c && <div className="rounded-lg bg-sage p-3">
            <p className="font-semibold">Predict: {c.predict.question}</p>
            {Object.entries(c.predict.options).map(([k, v]) => (
              <button key={k} disabled={!!picked} onClick={() => choose(k)} className={`mt-1 block w-full rounded-lg border p-2 text-left ${picked === k ? (pred?.correct ? "border-teal bg-teal/10" : "border-coral bg-coral/10") : "border-line bg-white"}`}>{k.toUpperCase()}. {v}</button>))}
            {pred && <p className="mt-1 text-sm">{pred.correct === null ? "Prediction already recorded for this case." : pred.correct ? "That matches the expert." : "Not what the expert would do. Try the record, I will stop you before it is saved."}</p>}
          </div>}
        </div>
        {result?.saved && (
          <div className="card space-y-2">
            <h3 className="font-bold">Saved. Mastery so far</h3>
            <table className="w-full text-sm"><tbody>{result.mastery.filter((m) => m.hinted || m.mean !== 0.5).map((m) => <tr key={m.rule_id}><td>{m.rule_id}</td><td>{m.level}</td><td>{(m.mean * 100).toFixed(0)}%</td><td>{m.hinted ? "needed a hint" : ""}</td></tr>)}</tbody></table>
            {result.next_scenario && <button className="btn btn-primary" onClick={() => open(result.next_scenario!)}>Next scenario: {result.next_scenario} (highest uncertainty × risk)</button>}
            {result.warnings.map((w) => <p key={w.rule_id} className="text-sm text-amber">Note: {w.message}</p>)}
          </div>)}
      </aside>
      {blocks && <Intercept blocks={blocks} onClose={() => setBlocks(null)} />}
    </div>
  );
}
