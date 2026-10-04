// Typed client for the Python engine. The browser never holds provider secrets.
export const ENGINE = process.env.NEXT_PUBLIC_ENGINE_URL ?? "http://localhost:8000";

export type Form = {
  incident_type: string; observation: string; interpretation: string; checks: string[];
  occurrences_today: number; months_in_residence: number; pattern: string; intervention: string; escalate_to: string;
};
export type CaseRecord = {
  resident: { name: string; age: number; diagnosis: string; in_residence: string };
  entries: { when: string; text: string; code: string }[]; facility_log: string; routine: string;
};
export type Scenario = { id?: string; title: string; resident: string; note: string; task?: string; facts?: string[]; record?: CaseRecord; form_start?: Partial<Form> };
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
export const COMPOSITE_NOTE = "composite case supplied by the startup team: invented details, not an interview";
export type Step = {
  n: number; step_id: string; rule_id: string; title: string; decision: string;
  screen_moment: { event_id: string; ts: number; text: string; form?: Partial<Form>; frame: boolean; vision?: string | null };
  reason: { text: string; ts: number; event_id: string; slot: string }[];
  rationale_seed: string; exceptions: { text: string; state: string }[];
  guardrails: { text: string; state: string; expert_words: Evidence[] }[];
  escalation: string; unresolved_slots: string[]; teach_back: string; provenance: Provenance[];
  related: Related[]; reviewed: string; review_note: string;
  confidence: { label: string; evidence_strength: string; evidence_count: number; source_class: string; teach_back: string; slot_states: string[]; caution: string; sessions: string[] };
};
export type Related = { unit_id: string; session: string; subtopic: string; source_type: string; score: number; branches: string[]; caveat: string };
export type Guideline = { source: string; page: number; excerpt: string; score: number };
export type CbtCheck = { formulation: boolean; targeted_intervention: boolean; measurement: boolean; empirical_validation: boolean; safeguards: Record<string, string> };
export type SeededRule = {
  rule_id: string; title: string; risk: number; context: string; action: string; rationale: string; escalation: string; predicate: string; severity: string;
  guardrails: { text: string; state: string }[]; evidence: Evidence[]; caution: string; confidence: string; related: Related[]; guidelines: Guideline[]; public: { url: string; excerpt: string; fetched_at: string; provider: string }[]; cbt: CbtCheck; reviewed: string; review_note: string;
};
export type LearnedCard = {
  id: string; title: string; kind: string; context: string; action: string; rationale: string; exceptions: string[]; guardrails: string[]; escalation: string[];
  safety_critical: boolean; cbt: { formulation: boolean; targeted_action: boolean; measures_response: boolean }; units: string[]; sessions: string[];
  evidence: { turn_id: string; span: string; unit_id: string; session: string }[]; evidence_status: string; corroboration: number;
  proposed_predicate: { all: { field: string; op: string; value: unknown }[] } | null; contradictions: { a: string; b: string; why: string }[];
  review: string; review_note: string; enforced: boolean;
};
export type LearnedMap = { cards: LearnedCard[]; agenda: { card: string; title: string; missing: string[]; ask: string }[]; report: Record<string, unknown> };
export type GraphNode = { id: string; type: string; label: string; status: string; detail: Record<string, unknown>; risk?: number; kind?: string; safety?: boolean; learned?: boolean };
export type GraphEdge = { source: string; target: string; type: string; label: string };
export type CareGraphData = { nodes: GraphNode[]; edges: GraphEdge[]; stats: { nodes: number; edges: number; by_type: Record<string, number>; rules_rederived_by_learner: string[]; map_version: string } };
export type Block = {
  rule_id: string; title: string; message: string; text: string; guardrail_id: string; evidence_class: string;
  trace: { field: string; op: string; expected: unknown; observed: unknown; met: boolean }[];
  explain: { expert_words: { kind: string; quote: string; unit_id?: string; turn?: string; ts?: number }[]; dataset_summaries: { summary: string; unit_id: string }[]; composite_cases?: { quote: string; unit_id: string }[]; screen_moment: { event_id: string; ts: number; frame: boolean } | null };
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
  session: (mode: "capture" | "teach") => call<{ id: string; capture_scenario: Scenario }>("/session", { mode }),
  cases: () => call<{ capture: Scenario; teach: { id: string; title: string }[] }>("/cases"),
  event: (e: { field: string; value?: unknown; delta?: unknown; form?: unknown }) => call<{ event: SandboxEvent; scope?: { escalate: boolean; reason: string } }>("/events", e),
  review: (rule_id: string, decision: "confirm" | "reject" | "reset", note = "") => call<{ rule_id: string; decision: string; map_version: string }>("/review", { rule_id, decision, note }),
  learned: () => call<LearnedMap>("/learned"),
  graph: () => call<CareGraphData>("/graph"),
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
