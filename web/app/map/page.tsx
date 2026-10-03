"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { LearnedMapPanel } from "@/components/LearnedMapPanel";
import { ENGINE, api, explain, sessionId, type Provenance, type Related, type SeededRule, type Step } from "@/lib/engine";

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

function ReviewBar({ rule, onChange }: { rule: SeededRule; onChange: () => void }) {
  const [note, setNote] = useState(rule.review_note ?? "");
  const act = async (d: "confirm" | "reject" | "reset") => { await api.review(rule.rule_id, d, note); onChange(); };
  return (
    <div className="mt-2 space-y-1 rounded-lg border border-line bg-paper p-2">
      <p className="text-xs">Expert review (you are the reviewer; saved on this machine and applied to Teach)
        {rule.reviewed === "confirmed" && <span className="chip ml-2 border-teal bg-teal text-white">confirmed by expert review</span>}
        {rule.reviewed === "rejected" && <span className="chip ml-2 border-coral text-coral">rejected: this rule no longer fires</span>}</p>
      <input className="w-full rounded border border-line px-2 py-1 text-sm" placeholder="Optional correction or note (e.g. an exception to add)" value={note} onChange={(e) => setNote(e.target.value)} />
      <div className="flex flex-wrap gap-2">
        <button className="btn btn-primary" onClick={() => act("confirm")}>Confirm this rule</button>
        <button className="btn btn-ghost" onClick={() => act("reject")}>Reject</button>
        {rule.reviewed && <button className="btn btn-ghost" onClick={() => act("reset")}>Undo review</button>}
      </div>
    </div>
  );
}

function RelatedList({ items }: { items: Related[] }) {
  if (!items.length) return null;
  return (
    <details className="text-sm"><summary className="cursor-pointer text-teal">Related expert knowledge from other interviews ({items.length})</summary>
      <p className="text-xs text-ink/70">Retrieved automatically from the whole transcript set. Not curated, not confirmed live; paraphrased dataset rules, not quotations.</p>
      <ul className="mt-1 space-y-1">{items.map((r) => (
        <li key={r.unit_id} className="rounded border border-line p-2"><span className="chip">{r.unit_id}</span> <span className="chip">{r.session}</span> <b>{r.subtopic}</b>
          {r.branches.map((b) => <p key={b} className="text-xs">• {b}</p>)}{r.caveat && <p className="text-xs text-ink/70">Caveat: {r.caveat}</p>}</li>))}</ul></details>
  );
}

function ProvRow({ p }: { p: Provenance }) {
  return p.kind === "screen"
    ? <li><span className="chip border-teal">screen moment</span> event {String(p.event_id)} at {Number(p.ts).toFixed(0)}s</li>
    : <li><span className="chip">transcript</span> {String(p.unit_id)} · {String(p.session)} · turns {(p.turn_ids as string[]).join(", ")} {p.verbatim ? <>(verbatim span): <i>“{String(p.span)}”</i></> : <>(dataset summary, not a quotation): <i>{String(p.span)}</i></>}</li>;
}

export default function WorkMap() {
  const [steps, setSteps] = useState<Step[]>([]);
  const [seeded, setSeeded] = useState<SeededRule[]>([]);
  const [version, setVersion] = useState("");
  const [unexplained, setUnexplained] = useState<{ event_id: string; ts: number; text: string }[]>([]);
  const [open, setOpen] = useState<string>("");
  const [err, setErr] = useState("");
  const load = () => api.workmap().then((w) => { setSteps(w.steps); setSeeded(w.seeded_rules); setVersion(w.map_version); setUnexplained(w.unexplained_events); }).catch((e) => setErr(explain(e)));
  useEffect(() => { api.workmap().then((w) => { setSteps(w.steps); setSeeded(w.seeded_rules); setVersion(w.map_version); setUnexplained(w.unexplained_events); setOpen(w.steps[0]?.step_id ?? ""); }).catch((e) => setErr(explain(e))); }, []);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Work Map <span className="chip ml-2" title="Content hash of the artifact the Teach step consumes">version {version}</span></h2>
        <div className="flex gap-2">
          <a href={`${ENGINE}/export?sid=${encodeURIComponent(sessionId())}`} className="btn btn-ghost" download>Export agent-ready guardrails</a>
          <Link href="/teach" className="btn btn-primary">Teach a new hire →</Link>
        </div>
      </div>
      {err && <p className="text-coral">{err}</p>}
      {!steps.length && !err && <p className="card">No live steps yet. Run Capture to add steps from what the apprentice sees and you explain. The seeded map from the expert transcripts is below.</p>}
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
                  <h4 className="font-semibold">Guardrails <span className="text-xs font-normal">(transcript evidence shown is for the rule, not for this exact guardrail)</span></h4>
                  {s.guardrails.map((g) => (
                    <div key={g.text} className="rounded-lg border border-amber bg-amber/10 p-2 text-sm">
                      <p>{g.text} <span className="chip">{g.state}</span></p>
                      {g.expert_words.map((w, i) => w.kind === "dataset_summary"
                        ? <p key={i} className="mt-1 text-xs"><span className="chip">dataset summary, not a quotation</span> {w.summary} ({w.unit_id})</p>
                        : <blockquote key={i} className="quote mt-1">“{String(w.quote ?? "")}” <span className="text-xs">({w.kind === "screen" ? "live" : `transcript ${w.unit_id}`})</span></blockquote>)}
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
                  <RelatedList items={s.related} />
                  <details><summary className="cursor-pointer text-teal">Provenance</summary><ul className="mt-1 list-disc space-y-1 pl-5 text-sm">{s.provenance.map((p, i) => <ProvRow key={i} p={p} />)}</ul></details>
                </div>
              </div>)}
          </li>))}
      </ol>
      {unexplained.length > 0 && <div className="card text-sm"><b>Demonstrated but not explained yet (missing, not guessed):</b> {unexplained.map((u) => `${u.ts.toFixed(0)}s ${u.text}`).join("; ")}.</div>}
      {seeded.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-lg font-bold">Seeded from expert transcripts <span className="chip ml-1">hypotheses, not yet confirmed live</span></h3>
          <p className="text-sm">Curated from the de-identified interviews. Each rule keeps its source span and starts as a hypothesis; a live capture turns it into expert-stated, a teach-back into confirmed.</p>
          {seeded.map((r) => (
            <details key={r.rule_id} className="card">
              <summary className="flex cursor-pointer flex-wrap items-center gap-2"><b>{r.title}</b>
                <span className={`chip ${LABEL_COLOR[r.confidence]}`}>confidence: {r.confidence}</span>{r.reviewed === "confirmed" && <span className="chip border-teal bg-teal text-white">expert-confirmed</span>}{r.reviewed === "rejected" && <span className="chip border-coral text-coral">rejected</span>}<span className="chip">risk {r.risk}/3</span><span className="chip">{r.rule_id}</span></summary>
              <div className="mt-2 grid gap-3 text-sm lg:grid-cols-2">
                <div className="space-y-1">
                  <p><b>Context:</b> {r.context}</p><p><b>Action:</b> {r.action}</p><p><b>Why:</b> {r.rationale}</p>
                  {r.escalation && <p><b>Hand over to:</b> {r.escalation}</p>}
                  <p className="font-mono text-xs">{r.severity === "block" ? "blocks Save when" : "warns when"}: {r.predicate}</p>
                </div>
                <div className="space-y-1">
                  {r.guardrails.map((g) => <p key={g.text} className="rounded border border-amber bg-amber/10 p-2">{g.text} <span className="chip">{g.state}</span></p>)}
                  {r.evidence.map((w, i) => w.kind === "dataset_summary"
                    ? <p key={i} className="text-xs"><span className="chip">dataset summary, not a quotation</span> {w.summary} ({w.unit_id})</p>
                    : <blockquote key={i} className="quote">“{w.quote}” <span className="text-xs">(transcript {w.unit_id}, verbatim)</span></blockquote>)}
                  {r.caution && <p className="text-xs text-ink/70">Caveat: {r.caution}</p>}
                  <RelatedList items={r.related} />
                  <ReviewBar rule={r} onChange={load} />
                </div>
              </div>
            </details>))}
        </section>)}
      <LearnedMapPanel />
    </div>
  );
}
