# Demo script: the wandering transfer story (6 minutes)

## The one-sentence story

An experienced carer shows the apprentice how they investigate Mr. D's new afternoon wandering; the apprentice captures the hidden reasoning and guardrails, freezes them into an inspectable Work Map, then stops a new hire from making the same category error on a different resident.

## Before the clock starts

- Engine on `:8000`, web on `:3000`, Chrome tab-share permission pre-granted, headset checked.
- Open `/capture`. Confirm the card says **Afternoon wandering — Mr. D**.
- Use fake data only. If voice fails, continue with captions and typed answers; call this the disclosed degraded path.
- Do not reveal the source micro-case answer chart to the judge. The product must reveal the reasoning.

## Spoken and clicked run-of-show

### 0:00–0:25 — Frame the challenge

Say: “A recorder can show that an expert clicked ‘wandering.’ We need the judgment behind what they check, what they refuse to assume, and when they hand over. I’ll teach that judgment once, then test it on a different resident.”

Point to the three-module journey: **Capture → Map → Teach**. Explain that Debrief completes Map; the evidence graph is an optional technical inspection, not another workflow stage.

### 0:25–2:10 — Capture Mr. D’s reasoning

1. Start voice and share this browser tab.
2. Read the task: the team asks whether this is sundowning and whether to request an antipsychotic.
3. Type the observation: `New corridor pacing and door-trying after the 15:00 drinks round; wet trousers on Day 3; calmed after bathroom on Day 6.`
4. While typing, point to the pause gate: the apprentice remains silent because hands/screen are active.
5. Choose **Wandering / pacing**, **New**, then check **Toileting**. At the natural pause, answer: “I check body and basic needs before naming a dementia behaviour. Here the timing, wet trousers and calming after the bathroom point to toileting.”
6. Check **Signage, routine, schedule changes**. Answer: “The plaques disappeared when the corridor was repainted. That is a new environmental cue loss, not proof of sundowning.”
7. Choose **Prompted toileting**, then explain: “Offer the bathroom after drinks and restore the cue; do not jump to medication. Escalate if physical concerns or deterioration appear.”

Say: “Each question is tied to the field change on screen, ranked by an unresolved reason or guardrail, and delayed until voice, hands and screen are quiet.”

### 2:10–3:05 — Debrief and teach-back

Answer three new follow-ups. Cover the remaining boundary, re-measurement, and an unseen variation. During teach-back, correct one item once, then confirm it.

Say: “Done means three new gaps addressed, guardrail coverage, and confirmed teach-back. It does not mean the model claims complete understanding.”

### 3:05–4:00 — Inspect the Work Map

Open **Map · Work Map** and stay on **Captured timeline**.

1. Open the wandering step.
2. Point left-to-right: captured screen moment → decision → literal live explanation → guardrail.
3. Open Provenance and say: “Live words, de-identified interview spans, dataset summaries, literature, and the supplied composite case are different source classes. A summary is never rendered as a quote. Composite details never masquerade as an interview.”
4. Point to the frozen map hash: “Teach evaluates this frozen artifact; later edits cannot silently change the lesson.”
5. Mention **Evidence & rule review** and **Technical evidence graph**, but do not open them unless a judge asks.

### 4:00–5:30 — Transfer test on R-327

Open **Teach**. The recommended case is **T4: Afternoon pacing at the corridor doors**. This is not Mr. D: it is a sealed case with a different resident, eight months in residence, dimmer lighting and missing glasses.

1. Predict **A — record sundowning and ask for an antipsychotic**.
2. Choose **Sundowning** and **Ask physician for an antipsychotic**, without completing body/basic-needs or environment checks.
3. Click **Save record**.
4. The tutor must stop the save. Point to the guardrail ID, matched fields, observed values, executable predicate and evidence class.
5. Say: “This is a pre-save intervention, not feedback after harm. The evidence panel stays honest if this rule has composite support but no live screen moment.”
6. Click **Fix it**. Change interpretation to **Unknown** or **Environmental**; check glasses/basic needs and environment/signage; choose an in-scope response and retry.
7. Point to mastery and the next scenario chosen by uncertainty × risk.

### 5:30–6:00 — Trust and close

Say: “Off the record stops collection immediately and deletes local events, frames, answers and derived items from the selected window. Provider-held data follows provider retention; we do not promise otherwise. The demo uses fake data and cropped form frames.”

Close: “The product does not automate a diagnosis. It transfers a professional method: observe, rule out needs and environment, resist premature labels, act within scope, and re-measure.”

## Recovery lines

- **Voice unavailable:** “The voice adapter is degraded; the same event-grounded question, answer and provenance path remains visible and testable.” Continue with typed answers.
- **Frame missing:** “The frame is unavailable, so the Map shows the immutable structured form state and labels the missing frame. It does not fabricate a replay.”
- **No live confirmation:** “This rule is transcript-seeded/composite-supported and visibly unconfirmed in this session; Teach does not relabel it as live expert evidence.”
- **Unexpected save succeeds:** use T4; verify `wandering`; choose `sundowning` plus `request_antipsychotic`; leave both check groups incomplete; save.

## Rehearsal gate

- [ ] Full engine tests, web lint/build and wandering E2E pass.
- [ ] One complete run under six minutes and one degraded-mode run.
- [ ] T4 starts by default; wrong path blocks before save; corrected path saves.
- [ ] Map defaults to Captured timeline; evidence library and graph do not dominate the story.
- [ ] Composite-case wording is visible anywhere composite details appear.
- [ ] No repository push; demo state reset after rehearsal.
