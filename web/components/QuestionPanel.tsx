"use client";
import type { Gate, Question } from "@/lib/engine";

const GATE_LABEL: Record<string, string> = { voice_silent: "Voice silent", hands_still: "Hands still", screen_stable: "Screen stable", cooldown_done: "Cooldown done", budget_ok: "Question budget" };
const TYPE_LABEL: Record<string, string> = { why: "Why", guardrail: "Guardrail", counterfactual: "Counterfactual", escalation: "Guardrail", unseen: "Unseen case", drift: "What changed?" };

export function PauseGate({ gate }: { gate: Gate }) {
  return (
    <div className="flex flex-wrap gap-1" aria-label="Pause gate">
      {Object.keys(GATE_LABEL).map((k) => (
        <span key={k} className={`chip ${gate[k] ? "border-teal bg-sage" : "border-coral text-coral"}`}>{gate[k] ? "●" : "○"} {GATE_LABEL[k]}</span>))}
    </div>
  );
}

export function QuestionCaption({ q, state }: { q: Question | null; state: "quiet" | "asking" | "waiting" }) {
  const ring = state === "asking" ? "ring-4 ring-amber animate-pulse" : state === "waiting" ? "ring-4 ring-teal/40" : "ring-2 ring-sage";
  const label = state === "asking" ? "Asking" : state === "waiting" ? "Listening for your answer" : "Listening quietly";
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <div className={`h-12 w-12 rounded-full bg-teal ${ring}`} aria-hidden />
        <div className="font-semibold">{label}</div>
      </div>
      {q ? (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2">
            <span className="chip bg-amber/20">{TYPE_LABEL[q.type] ?? q.type}</span>
            <span className="chip">slot: {q.slot}</span>
            {q.event_text && <span className="chip">About: {q.event_text}</span>}
          </div>
          <p className="text-xl leading-snug" role="status">{q.text}</p>
          {q.alternatives.length > 0 && (
            <details className="text-sm"><summary className="cursor-pointer text-teal">Why this one? Ranked missing slots</summary>
              <ol className="list-decimal pl-5">
                <li><b>{q.rule_id} / {q.slot}</b> score {q.score} (chosen)</li>
                {q.alternatives.map((a) => <li key={a.rule_id + a.slot}>{a.rule_id} / {a.slot} score {a.score}</li>)}
              </ol>
              <p className="text-xs">Risk-weighted expected uncertainty reduction over slot states. Not calibrated information gain.</p></details>)}
        </div>
      ) : <p className="text-sm text-ink/70">Staying quiet while you work. I will only ask at a natural pause, about something on your screen.</p>}
    </div>
  );
}
