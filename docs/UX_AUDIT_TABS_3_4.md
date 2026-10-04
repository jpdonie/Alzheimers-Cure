# Tabs 3–4 UX and brief-alignment audit

## Verdict

The previous five-step navigation made implementation surfaces look like user tasks: Debrief, Work Map and Graph competed as separate numbered stages, while the challenge asks for three modules—Capture, Map and Teach. The Map page also exposed the entire seeded rule library immediately, making the required clickable captured timeline hard to find. Teach opened on a legacy refusal scenario instead of the wandering transfer story.

## Changes made

| Problem | Change | Brief proof made easier |
|---|---|---|
| Five numbered steps contradicted three modules | Four task tabs: Capture; Map · Debrief; Map · Work Map; Teach. Graph is linked as a technical view. | Judges can map the UI to Capture, Map, Teach without translation. |
| Work Map mixed the required timeline with research/admin content | Default `Captured timeline`; separate `Evidence & rule review`; graph is optional. | Screen moment, decision, expert words and guardrail are the first path. |
| Provenance was present but cognitively buried | Map header exposes the frozen artifact hash; source classes remain explicit at the evidence item. | Trust and exact-artifact reuse are inspectable without implying equal evidence quality. |
| Teach lacked a clear sequence | Added module header and Predict → Document → Save & reflect orientation. | The required predict-first and pre-save catch are legible. |
| Demo defaulted to an unrelated case | Teach defaults to T4, a materially different wandering case. | Shows transfer from Mr. D rather than replaying the captured case. |

## Evidence hierarchy used in the UI

1. **Live capture:** literal answer tied to an event and, when available, a cropped frame.
2. **De-identified transcript:** verbatim only when the span is code-verified; otherwise labelled dataset summary.
3. **Composite case:** invented exercise details, never an interview and never independent corroboration.
4. **Guideline/literature context:** supporting context, not an expert quote and not proof of local effectiveness.
5. **Missing:** shown as missing or degraded, never inferred into provenance.

## Research basis

The redesign uses progressive disclosure to keep the judge on the primary task, a task-oriented sequence with visible status, and a modal intervention that must receive and contain keyboard focus. References: W3C cognitive accessibility guidance on removing unnecessary distractions; GOV.UK task-list guidance on explicit task status; WAI-ARIA modal-dialog guidance on focus and inert background.

## Modal intervention

The pre-save intercept now uses the native HTML `dialog` element. The browser makes the background inert, contains focus, supports Escape, and returns focus to the invoking Save control. The visible heading labels the dialog. This follows the W3C H102 technique; it still requires keyboard/browser testing before any broad accessibility-conformance claim.
