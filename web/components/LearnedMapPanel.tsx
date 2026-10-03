"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, explain, type LearnedCard, type LearnedMap } from "@/lib/engine";

const KIND_LABEL: Record<string, string> = { decision_rule: "Decision rule", escalation_rule: "Escalation rule", principle: "Principle", process: "Process", measurement: "Measurement", other: "Other" };
const num = (v: unknown) => (typeof v === "number" ? v : 0);

function predText(c: LearnedCard) { return c.proposed_predicate?.all.map((x) => `${x.field} ${x.op} ${JSON.stringify(x.value)}`).join(" AND ") ?? ""; }

function Card({ c, onChange }: { c: LearnedCard; onChange: () => void }) {
  const act = async (d: "confirm" | "reject" | "reset") => { await api.review(c.id, d); onChange(); };
  return (
    <details className="card">
      <summary className="flex cursor-pointer flex-wrap items-center gap-2">
        <b>{c.title}</b><span className="chip">{KIND_LABEL[c.kind] ?? c.kind}</span>
        {c.safety_critical && <span className="chip border-coral text-coral">safety-critical</span>}
        {c.corroboration >= 2 && <span className="chip border-teal">{c.corroboration} sessions agree</span>}
        {c.review === "confirm" && <span className="chip border-teal bg-teal text-white">accepted{c.enforced ? ", warns in Teach" : ""}</span>}
        {c.review === "reject" && <span className="chip border-coral text-coral">rejected</span>}
      </summary>
      <div className="mt-2 grid gap-3 text-sm lg:grid-cols-2">
        <div className="space-y-1">
          <p><b>Context:</b> {c.context || "not stated"}</p><p><b>Action:</b> {c.action || "not stated"}</p><p><b>Why:</b> {c.rationale || "not stated"}</p>
          <p><b>Exceptions:</b> {c.exceptions.join("; ") || <span className="text-coral">none stated in the interviews</span>}</p>
          <p><b>Escalation:</b> {c.escalation.join("; ") || <span className="text-coral">none stated</span>}</p>
          {c.proposed_predicate && <p className="font-mono text-xs">proposed check (unreviewed): warns when {predText(c)}</p>}
          {c.contradictions.map((x, i) => <p key={i} className="text-xs text-coral">Possible conflict {x.a} vs {x.b}: {x.why}</p>)}
        </div>
        <div className="space-y-1">
          {c.guardrails.map((g) => <p key={g} className="rounded border border-amber bg-amber/10 p-2">{g}</p>)}
          {c.evidence.slice(0, 3).map((e, i) => <blockquote key={i} className="quote">“{e.span}” <span className="text-xs">({e.unit_id}, {e.turn_id}, verbatim, checked by code)</span></blockquote>)}
          {c.evidence_status !== "verbatim-verified" && <p className="text-xs text-coral">No verbatim span could be verified for this card: summary only.</p>}
          <p className="text-xs">CBT rubric: formulation {c.cbt.formulation ? "✓" : "○"} · targeted action {c.cbt.targeted_action ? "✓" : "○"} · measures response {c.cbt.measures_response ? "✓" : "○"}</p>
          <div className="flex flex-wrap gap-2 pt-1">
            <button className="btn btn-primary" onClick={() => act("confirm")}>Accept</button>
            <button className="btn btn-ghost" onClick={() => act("reject")}>Reject</button>
            {c.review && <button className="btn btn-ghost" onClick={() => act("reset")}>Undo</button>}
          </div>
          {!c.proposed_predicate && <p className="text-xs text-ink/70">Accepting records the review; this card has no checkable predicate, so it informs the tutor but never fires.</p>}
        </div>
      </div>
    </details>
  );
}

/** What the apprentice learned from ALL interview units, with human review. Accepted cards with a validated predicate warn in Teach. */
export function LearnedMapPanel() {
  const [d, setD] = useState<LearnedMap | null>(null);
  const [err, setErr] = useState("");
  const [kind, setKind] = useState("decision_rule");
  const load = useCallback(() => { api.learned().then(setD).catch((e) => setErr(explain(e))); }, []);
  useEffect(() => { load(); }, [load]);
  const shown = useMemo(() => (d?.cards ?? []).filter((c) => kind === "all" || (kind === "safety" ? c.safety_critical : kind === "checkable" ? !!c.proposed_predicate : c.kind === kind)), [d, kind]);
  if (err) return <p className="text-coral">{err}</p>;
  if (!d || !d.cards.length) return <p className="card text-sm">The learned map is not built on this machine. Run <code>python -m engine.learner extract</code> then <code>merge</code> (needs the transcript file and an Anthropic key).</p>;
  const r = d.report as Record<string, unknown>;
  return (
    <section className="space-y-2">
      <h3 className="text-lg font-bold">Learned from all interview transcripts <span className="chip ml-1">{d.cards.length} cards · unreviewed until you accept</span></h3>
      <p className="text-sm">The apprentice read every usable interview unit and extracted decision cards. Quoted spans were checked by code to be literal text from the cited turn. {num(r.verbatim_verified)} of {d.cards.length} cards have a verified span; {num(r.corroborated_2plus_sessions)} are corroborated by 2+ sessions; only {num(r.with_exceptions)} state any exception, which is the biggest gap in the data.</p>
      <div className="flex flex-wrap gap-1">
        {[["decision_rule", "Decision rules"], ["escalation_rule", "Escalation"], ["checkable", "Checkable"], ["safety", "Safety-critical"], ["principle", "Principles"], ["process", "Process"], ["measurement", "Measurement"], ["all", "All"]].map(([k, l]) => (
          <button key={k} onClick={() => setKind(k)} className={`chip ${kind === k ? "bg-teal text-white" : ""}`}>{l}</button>))}
      </div>
      <div className="space-y-2">{shown.map((c) => <Card key={c.id} c={c} onChange={load} />)}</div>
      {d.agenda.length > 0 && (
        <div className="card text-sm"><b>What to ask an expert next (largest gaps in the corpus)</b>
          <ol className="list-decimal pl-5">{d.agenda.slice(0, 6).map((g) => <li key={g.card}>{g.title}: <i>{g.ask}</i> <span className="text-ink/60">(missing: {g.missing.join(", ")})</span></li>)}</ol></div>)}
    </section>
  );
}
