"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type Provenance, type Step } from "@/lib/engine";

const LABEL_COLOR: Record<string, string> = { low: "border-coral text-coral", medium: "border-amber bg-amber/20", high: "border-teal bg-teal text-white" };

function Frame({ id, form }: { id: string; form?: Record<string, unknown> }) {
  const [bad, setBad] = useState(false);
  return (
    <div className="space-y-1">
      {!bad && <img src={api.frameUrl(id)} alt="Captured screen moment" className="max-h-64 rounded border border-line" onError={() => setBad(true)} />}
      {bad && <p className="text-xs text-ink/70">No frame captured (degraded mode). Form state at that moment:</p>}
      {form && <table className="text-xs"><tbody>{Object.entries(form).map(([k, v]) => <tr key={k}><td className="pr-2 font-semibold">{k}</td><td>{JSON.stringify(v)}</td></tr>)}</tbody></table>}
    </div>
  );
}

function ProvRow({ p }: { p: Provenance }) {
  return p.kind === "screen"
    ? <li><span className="chip border-teal">screen moment</span> event {String(p.event_id)} at {Number(p.ts).toFixed(0)}s</li>
    : <li><span className="chip">transcript</span> {String(p.unit_id)} · {String(p.session)} · turns {(p.turn_ids as string[]).join(", ")} {p.verbatim ? "(verbatim span)" : "(dataset summary)"}: <i>“{String(p.span)}”</i></li>;
}

export default function WorkMap() {
  const [steps, setSteps] = useState<Step[]>([]);
  const [seeded, setSeeded] = useState<string[]>([]);
  const [version, setVersion] = useState("");
  const [open, setOpen] = useState<string>("");
  const [err, setErr] = useState("");
  useEffect(() => { api.workmap().then((w) => { setSteps(w.steps); setSeeded(w.seeded_only_rules); setVersion(w.map_version); setOpen(w.steps[0]?.step_id ?? ""); }).catch(() => setErr("Engine not reachable on :8000")); }, []);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Work Map <span className="chip ml-2" title="Content hash of the artifact the Teach step consumes">version {version}</span></h2>
        <Link href="/teach" className="btn btn-primary">Teach a new hire →</Link>
      </div>
      {err && <p className="text-coral">{err}</p>}
      {!steps.length && !err && <p className="card">No steps yet. Run Capture first: the map is built from what the apprentice saw and what you explained.</p>}
      <ol className="space-y-3">
        {steps.map((s) => (
          <li key={s.step_id} className="card">
            <button className="flex w-full flex-wrap items-center gap-2 text-left" onClick={() => setOpen(open === s.step_id ? "" : s.step_id)}>
              <span className="chip bg-teal text-white">Step {s.n}</span><b>{s.title}</b>
              <span className={`chip ${LABEL_COLOR[s.confidence.label]}`}>confidence: {s.confidence.label}</span>
              {s.guardrails.slice(0, 1).map((g) => <span key={g.text} className="chip border-amber bg-amber/20">guardrail</span>)}
            </button>
            {open === s.step_id && (
              <div className="mt-3 grid gap-4 lg:grid-cols-2">
                <div className="space-y-2">
                  <h4 className="font-semibold">Screen moment</h4>
                  <p className="text-sm">{s.screen_moment.ts.toFixed(0)}s · expert {s.decision}</p>
                  <Frame id={s.screen_moment.event_id} form={s.screen_moment.form as Record<string, unknown>} />
                  {s.screen_moment.vision && <p className="text-xs">Vision model caption: {s.screen_moment.vision}</p>}
                  <h4 className="font-semibold">In the expert&apos;s words (live)</h4>
                  {s.reason.length ? s.reason.map((r, i) => <blockquote key={i} className="quote">“{r.text}” <span className="text-xs">({r.slot}, {r.ts.toFixed(0)}s)</span></blockquote>) : <p className="text-sm text-coral">No live explanation yet. Missing, not guessed.</p>}
                  <h4 className="font-semibold">Why (seeded from transcripts, not yet confirmed live)</h4>
                  <p className="text-sm">{s.rationale_seed}</p>
                </div>
                <div className="space-y-2">
                  <h4 className="font-semibold">Guardrails</h4>
                  {s.guardrails.map((g) => (
                    <div key={g.text} className="rounded-lg border border-amber bg-amber/10 p-2 text-sm">
                      <p>{g.text} <span className="chip">{g.state}</span></p>
                      {g.expert_words.map((w, i) => <blockquote key={i} className="quote mt-1">“{String(w.quote ?? "")}” <span className="text-xs">({w.kind === "screen" ? "live" : `transcript ${w.unit_id}`})</span></blockquote>)}
                    </div>))}
                  {s.exceptions.length > 0 && <><h4 className="font-semibold">Exceptions the expert named</h4><ul className="list-disc pl-5 text-sm">{s.exceptions.map((e) => <li key={e.text}>{e.text}</li>)}</ul></>}
                  {s.escalation && <p className="text-sm"><b>Hand over to:</b> {s.escalation}</p>}
                  <h4 className="font-semibold">Evidence facets</h4>
                  <div className="flex flex-wrap gap-1 text-xs">
                    <span className="chip">evidence: {s.confidence.evidence_strength} ({s.confidence.evidence_count})</span>
                    <span className="chip">source: {s.confidence.source_class}</span>
                    <span className="chip">teach-back: {s.confidence.teach_back}</span>
                    <span className="chip">still open: {s.unresolved_slots.join(", ") || "none"}</span>
                  </div>
                  {s.confidence.caution && <p className="text-xs text-ink/70">Caveat: {s.confidence.caution}</p>}
                  <details><summary className="cursor-pointer text-teal">Provenance</summary><ul className="mt-1 list-disc space-y-1 pl-5 text-sm">{s.provenance.map((p, i) => <ProvRow key={i} p={p} />)}</ul></details>
                </div>
              </div>)}
          </li>))}
      </ol>
      {seeded.length > 0 && <div className="card text-sm"><b>Known from transcripts only, never seen live:</b> {seeded.join(", ")}. These are hypotheses until an expert confirms them.</div>}
    </div>
  );
}
