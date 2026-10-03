"use client";
import { useRef, type ReactNode } from "react";
import type { Form } from "@/lib/engine";

export const EMPTY: Form = { incident_type: "refusal_of_care", observation: "", interpretation: "none", checks: [], occurrences_today: 1, pattern: "", intervention: "no_action", escalate_to: "none" };
const CHECKS = [["pain", "Pain / physical discomfort"], ["footwear_skin", "Feet, footwear, skin"], ["hunger_thirst", "Hunger / thirst"], ["hearing_vision_aids", "Hearing aids / glasses"], ["noise_environment", "Noise / environment"], ["toileting", "Toileting"]];
const opts = (pairs: string[][]) => pairs.map(([v, l]) => <option key={v} value={v}>{l}</option>);

type Props = {
  resident: string; form: Form; onChange: (next: Form, field: string, delta?: { added?: string; removed?: string }) => void;
  onSave: () => void; onActivity?: () => void; facts?: string[]; lockedType?: boolean; saveLabel?: string; children?: ReactNode;
};

/** Fake care-records page. Every edit is reported as a DOM event; this is the primary MVP sensor. */
export function CareRecordSandbox({ resident, form, onChange, onSave, onActivity, facts, lockedType, saveLabel = "Save record", children }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const set = <K extends keyof Form>(k: K, v: Form[K], delta?: { added?: string; removed?: string }) => onChange({ ...form, [k]: v }, k, delta);
  const L = "block text-sm font-semibold mb-1";
  const I = "w-full rounded-lg border border-line bg-white px-3 py-2";
  return (
    <div ref={ref} id="sandbox" className="card space-y-3" onKeyDown={onActivity} onPointerMove={onActivity} onPointerDown={onActivity}>
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">Care Records · Incident note</h2>
        <span className="chip">Resident {resident} (fake data)</span>
      </div>
      {facts && <ul className="text-sm bg-sage rounded-lg p-3 list-disc pl-6">{facts.map((f) => <li key={f}>{f}</li>)}</ul>}
      <div className="grid grid-cols-2 gap-3">
        <label><span className={L}>Incident type</span>
          <select disabled={lockedType} className={I} value={form.incident_type} onChange={(e) => set("incident_type", e.target.value)}>
            {opts([["refusal_of_care", "Refusal of care"], ["exit_seeking", "Exit-seeking"], ["medication_request", "Medication request"], ["other", "Other"]])}
          </select></label>
        <label><span className={L}>Occurrences today</span>
          <input type="number" min={0} className={I} value={form.occurrences_today} onChange={(e) => set("occurrences_today", Number(e.target.value))} /></label>
      </div>
      <label><span className={L}>What you observed (facts only)</span>
        <textarea className={I} rows={2} value={form.observation} onChange={(e) => set("observation", e.target.value)} /></label>
      <label><span className={L}>Your interpretation</span>
        <select className={I} value={form.interpretation} onChange={(e) => set("interpretation", e.target.value)}>
          {opts([["none", "None yet"], ["behavioural_agitation", "Behavioural: agitation"], ["physical_cause_suspected", "Physical cause suspected"], ["environmental", "Environmental"], ["unknown", "Unknown"]])}
        </select></label>
      <fieldset><legend className={L}>Checks done</legend>
        <div className="grid grid-cols-2 gap-1">
          {CHECKS.map(([v, l]) => (
            <label key={v} className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.checks.includes(v)}
                onChange={(e) => set("checks", e.target.checked ? [...form.checks, v] : form.checks.filter((x) => x !== v), e.target.checked ? { added: v } : { removed: v })} />{l}
            </label>))}
        </div></fieldset>
      <div className="grid grid-cols-3 gap-3">
        <label><span className={L}>Behaviour is</span>
          <select className={I} value={form.pattern} onChange={(e) => set("pattern", e.target.value)}>{opts([["", "Select"], ["new", "New"], ["habitual", "Habitual"], ["unsure", "Unsure"]])}</select></label>
        <label><span className={L}>Intervention</span>
          <select className={I} value={form.intervention} onChange={(e) => set("intervention", e.target.value)}>
            {opts([["no_action", "No action"], ["retry_later_same_carer", "Retry later, same carer"], ["swap_carer_or_call_psychologist", "Swap carer / call psychologist"], ["reassure_and_note", "Reassure and note"], ["give_prn_medication", "Give PRN medication"], ["adjust_diet", "Adjust diet"], ["integration_plan_review", "Review integration plan"]])}
          </select></label>
        <label><span className={L}>Escalate to</span>
          <select className={I} value={form.escalate_to} onChange={(e) => set("escalate_to", e.target.value)}>
            {opts([["none", "Nobody"], ["nurse", "Nurse"], ["psychologist", "Psychologist"], ["team_meeting", "Team meeting"], ["coordinating_physician", "Coordinating physician"]])}
          </select></label>
      </div>
      {children}
      <button className="btn btn-primary" onClick={onSave}>{saveLabel}</button>
    </div>
  );
}
