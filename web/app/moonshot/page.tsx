"use client";
import { useEffect, useState } from "react";

type Sys = { "recall@3": number; correct_abstention_rate: number; escalation_recall_flagged: number; coverage: number };
type Pitch = {
  eval: Record<string, Sys | null>; eval_n: number; dp: { eps: number; mae: number }[]; drift: { steps: { event: string; apprentice: string }[] };
  learner: { merged_cards: number; by_kind: Record<string, number>; verbatim_verified: number; with_guardrails: number; with_exceptions: number; corroborated_2plus_sessions: number; cbt_all_three: number; safety_critical: number };
};

const NAMES: Record<string, string> = { bm25: "Keyword (BM25)", tfidf: "Text similarity", "tfidf+scope": "Similarity + safety lexicon", care_map: "Care Map", "care_map+scope": "Care Map + safety lexicon" };

function Bars({ d, metric, title }: { d: Pitch["eval"]; metric: keyof Sys; title: string }) {
  const rows = Object.entries(d).filter(([, v]) => v);
  return (
    <figure>
      <figcaption className="mb-1 text-sm font-semibold">{title}</figcaption>
      <svg viewBox="0 0 320 120" className="w-full" role="img" aria-label={title}>
        {rows.map(([k, v], i) => (
          <g key={k} transform={`translate(0 ${i * 22})`}>
            <text x="0" y="13" fontSize="9" fill="currentColor">{NAMES[k]}</text>
            <rect x="130" y="3" width={Math.max(1, (v as Sys)[metric] * 170)} height="13" rx="3" fill={k.startsWith("care_map") ? "#0f4c5c" : "#9bb5b0"} />
            <text x={134 + (v as Sys)[metric] * 170} y="13" fontSize="9" fill="currentColor">{(v as Sys)[metric].toFixed(2)}</text>
          </g>))}
      </svg>
    </figure>
  );
}

function DpChart({ dp }: { dp: Pitch["dp"] }) {
  const max = Math.max(...dp.map((p) => p.mae)); const xs = (i: number) => 20 + (i * 270) / (dp.length - 1); const ys = (m: number) => 100 - (m / max) * 85;
  return (
    <figure>
      <figcaption className="mb-1 text-sm font-semibold">Privacy vs error (simulation): mean error of shared rule counts</figcaption>
      <svg viewBox="0 0 320 130" className="w-full" role="img" aria-label="DP epsilon versus mean absolute error">
        <polyline fill="none" stroke="#0f4c5c" strokeWidth="2" points={dp.map((p, i) => `${xs(i)},${ys(p.mae)}`).join(" ")} />
        {dp.map((p, i) => <g key={p.eps}><circle cx={xs(i)} cy={ys(p.mae)} r="3" fill="#e8a33d" /><text x={xs(i) - 8} y="118" fontSize="9" fill="currentColor">ε {p.eps}</text><text x={xs(i) - 6} y={ys(p.mae) - 6} fontSize="9" fill="currentColor">{p.mae.toFixed(1)}</text></g>)}
      </svg>
    </figure>
  );
}

export default function Moonshot() {
  const [d, setD] = useState<Pitch | null>(null);
  useEffect(() => { fetch("/pitch-data.json").then((r) => r.json()).then(setD).catch(() => setD(null)); }, []);
  if (!d) return <p className="card">Run <code>python -m engine.build_pitch</code> to generate the slide data.</p>;
  const L = d.learner;
  return (
    <article className="space-y-4">
      <header>
        <h1 className="text-3xl font-bold text-teal">Moonshot: a living, privacy-preserving care memory</h1>
        <p className="text-lg">Today: one expert, one workflow, one hire, with provenance and a tested Save blocker. Next: every organisation keeps its person-level Care Maps local, and only noised rule-level aggregates are shared.</p>
      </header>
      <div className="grid gap-4 lg:grid-cols-3">
        <section className="card space-y-2">
          <h2 className="font-bold">The apprentice read every interview</h2>
          <p className="text-sm">{L.merged_cards} learned cards from the transcripts, {L.verbatim_verified} with spans checked by code as literal expert text. {L.with_guardrails} state a guardrail, but only {L.with_exceptions} state any exception and only {L.cbt_all_three} meet the full CBT rubric: the data tells us exactly what to ask experts next.</p>
          <p className="text-sm">{L.corroborated_2plus_sessions} cards are corroborated by 2+ sessions; {L.safety_critical} are safety-critical. Nothing is trusted until a person accepts it.</p>
        </section>
        <section className="card space-y-2">
          <h2 className="font-bold">Held-out test: learn from some sessions, test on unseen ones</h2>
          <Bars d={d.eval} metric="escalation_recall_flagged" title="Clinical queries escalated to a human" />
          <Bars d={d.eval} metric="correct_abstention_rate" title="Out-of-knowledge queries correctly not answered" />
          <p className="text-xs">{d.eval_n} queries, 5 leave-session-group-out folds, LLM-adjudicated labels. Plain similarity beats the Care Map on Recall@3 ({d.eval.tfidf?.["recall@3"]} vs {d.eval.care_map?.["recall@3"]}): the value is provenance and safe behaviour, not retrieval.</p>
        </section>
        <section className="card space-y-2">
          <h2 className="font-bold">Shared knowledge without pooled transcripts</h2>
          <DpChart dp={d.dp} />
          <p className="text-xs">Simulation only: 8 organisations, privacy unit = organisation, clipped rule-support vectors, Laplace noise. Not federated learning.</p>
        </section>
      </div>
      <section className="card">
        <h2 className="font-bold">Drift: when new behaviour contradicts a learned rule, ask what changed</h2>
        <ol className="mt-2 grid gap-2 text-sm lg:grid-cols-3">{d.drift.steps.map((s, i) => <li key={i} className="rounded-lg bg-sage p-2"><b>{s.event}</b><p className="mt-1">{s.apprentice}</p></li>)}</ol>
      </section>
      <p className="text-sm"><b>Not claimed today:</b> real federated training, clinical validation, automatic enforcement of learned rules without human acceptance.</p>
    </article>
  );
}
