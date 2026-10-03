// Typed client for the Python engine. The browser never holds provider secrets.
export const ENGINE = process.env.NEXT_PUBLIC_ENGINE_URL ?? "http://localhost:8000";

export type Form = {
  incident_type: string; observation: string; interpretation: string; checks: string[];
  occurrences_today: number; pattern: string; intervention: string; escalate_to: string;
};
export type SandboxEvent = {
  id: string; ts: number; text: string; field: string; value?: unknown; form?: Partial<Form>;
};
export type Question = {
  id: string; text: string; type: string; rule_id: string; slot: string; event_id: string | null;
  event_text: string | null; score: number; alternatives: { rule_id: string; slot: string; score: number }[];
};
export type Gate = Record<string, boolean>;
export type Provenance = Record<string, unknown> & { kind: string };
export type Evidence = { kind: string; quote?: string; summary?: string; unit_id?: string; ts?: number };
export type Step = {
  n: number; step_id: string; rule_id: string; title: string; decision: string;
  screen_moment: { event_id: string; ts: number; text: string; form?: Partial<Form>; frame: boolean; vision?: string | null };
  reason: { text: string; ts: number; event_id: string; slot: string }[];
  rationale_seed: string; exceptions: { text: string; state: string }[];
  guardrails: { text: string; state: string; expert_words: Evidence[] }[];
  escalation: string; unresolved_slots: string[]; teach_back: string; provenance: Provenance[];
  confidence: { label: string; evidence_strength: string; evidence_count: number; source_class: string; teach_back: string; slot_states: string[]; caution: string; sessions: string[] };
};
export type SeededRule = {
  rule_id: string; title: string; risk: number; context: string; action: string; rationale: string; escalation: string; predicate: string; severity: string;
  guardrails: { text: string; state: string }[]; evidence: Evidence[]; caution: string; confidence: string;
};
export type Block = {
  rule_id: string; title: string; message: string; text: string; guardrail_id: string; evidence_class: string;
  trace: { field: string; op: string; expected: unknown; observed: unknown; met: boolean }[];
  explain: { expert_words: { kind: string; quote: string; unit_id?: string; turn?: string; ts?: number }[]; dataset_summaries: { summary: string; unit_id: string }[]; screen_moment: { event_id: string; ts: number; frame: boolean } | null };
};

export class EngineError extends Error {
  constructor(message: string, public status: number) { super(message); }
}
/** Human-readable text for a failed engine call: separates "engine down" from "engine said no". */
export function explain(e: unknown): string {
  return e instanceof EngineError ? e.message : "Engine not reachable on :8000 (start it with uvicorn engine.api:app --port 8000).";
}

/** One id per browser tab: the engine keeps a separate session (and Off-the-record flag) for each. */
export function sessionId(): string {
  try {
    let id = sessionStorage.getItem("apprentice-sid");
    if (!id) { id = crypto.randomUUID(); sessionStorage.setItem("apprentice-sid", id); }
    return id;
  } catch { return "default"; }
}

async function call<T>(path: string, body?: unknown, method = body ? "POST" : "GET"): Promise<T> {
  const r = await fetch(`${ENGINE}${path}`, { method, headers: { "content-type": "application/json", "x-session-id": sessionId() }, body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) {
    let detail = `${r.status}`;
    try { detail = (await r.json()).detail ?? detail; } catch { /* non-JSON error body */ }
    throw new EngineError(String(detail), r.status);
  }
  return r.json();
}
export const api = {
  health: () => call<{ ok: boolean; degraded: boolean; usage: { calls: number; est_usd: number } }>("/health"),
  session: (mode: "capture" | "teach") => call<{ id: string; capture_scenario: { title: string; resident: string; facts: string[]; note: string } }>("/session", { mode }),
  cases: () => call<{ capture: { title: string; resident: string; facts: string[]; note: string }; teach: { id: string; title: string }[] }>("/cases"),
  event: (e: { field: string; value?: unknown; delta?: unknown; form?: unknown }) => call<{ event: SandboxEvent; scope?: { escalate: boolean; reason: string } }>("/events", e),
  recording: (on: boolean) => call<{ recording: boolean }>("/recording", { on }),
  frame: (event_id: string, data_url: string) => call("/frames", { event_id, data_url }),
  question: (event_id: string, signals: Gate) => call<{ question: Question | null; reason: string; gate: Gate }>("/question", { event_id, signals }),
  answer: (question_id: string, text: string) => call<{ transition: { slot: string; before: string; after: string }; dont_know: boolean; uncertainty: number }>("/answer", { question_id, text }),
  debriefStart: () => call<{ gaps: Question[]; questions: Question[] }>("/debrief/start", {}),
  debriefStatus: () => call<{ new_followups_answered: number; needs_3_new: boolean; guardrails_covered: boolean; teach_back_done: boolean; done: boolean; note: string; residual_gaps: { rule_id: string; slot: string }[] }>("/debrief/status"),
  teachback: () => call<{ text: string; steps: { step_id: string; rule_id: string; summary: string }[] }>("/debrief/teachback"),
  confirm: (rule_id: string, ok: boolean, correction?: string) => call<{ teach_back: string }>("/debrief/confirm", { rule_id, ok, correction }),
  workmap: () => call<{ map_version: string; steps: Step[]; seeded_only_rules: string[]; seeded_rules: SeededRule[]; unexplained_events: { event_id: string; ts: number; text: string }[] }>("/workmap"),
  offRecord: (since_ts: number) => call<{ events: number; frames: number; answers: number; slot_items: number; disclosure: string }>("/off-record", { since_ts }),
  teachOpen: (case_id: string) => call<{ map_version: string; map_confirmed: boolean; id: string; resident: string; title: string; facts: string[]; predict: { question: string; options: Record<string, string> }; form_start: Partial<Form> }>("/teach/open", { case_id }),
  predict: (case_id: string, option: string) => call<{ correct: boolean; explain: unknown }>("/teach/predict", { case_id, option }),
  checkSave: (case_id: string, form: Partial<Form>) => call<{ saved: boolean; blocked: Block[]; warnings: { rule_id: string; message: string }[]; mastery: { rule_id: string; mean: number; level: string; hinted: number }[]; next_scenario: string | null }>("/teach/check-save", { case_id, form }),
  brief: (case_id: string) => call<{ brief: string }>("/teach/brief", { case_id }),
  frameUrl: (id: string) => `${ENGINE}/frame/${id}?sid=${encodeURIComponent(sessionId())}`,
};
