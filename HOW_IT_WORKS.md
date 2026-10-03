# How Apprentice works (for teammates and judges)

Apprentice learns **why** an expert documents and escalates a dementia-care refusal incident, keeps every learned rule traceable to the exact moment it was learned, and teaches a new caregiver on a case the expert never showed. It is training and documentation support, not diagnosis or treatment.

## The flow

| Step | What happens | Where in code |
|---|---|---|
| 0. Seed | A Care Map is seeded from de-identified expert interviews: 6 curated rules, each a card [context, action, rationale, exceptions, guardrails, escalation] with source spans. Everything starts as a **hypothesis**. | `engine/care_map/demo_rules.json` |
| 1. Capture | The expert shares the tab and handles a fake incident. Every form edit is an event; frames are cropped to the form; a vision model confirms the decision-relevant ones. The agent stays silent until a pause (voice silent, hands still, screen stable, cooldown done, budget left), then asks about **that screen event** only. | `engine/session.py`, `web/app/capture` |
| 2. Debrief | A batched scan of the whole map ranks the top 3 unresolved slots that were not asked in the task, plus one rule for a case it has not seen. Then a teach-back: the apprentice explains the process, the expert confirms or corrects each step. | `engine/slots.py`, `web/app/debrief` |
| 3. Work Map | A clickable timeline. Each step: screen moment (frame), decision, the expert's literal words, guardrails, evidence facets, provenance (screen vs transcript). Below it: the seeded rules not yet seen live. | `web/app/map` |
| 4. Teach | A frozen copy of the map (content hash shown) coaches a new hire on sealed cases. They **predict first**; a wrong Save is stopped **before it is saved**, showing the guardrail, matched fields, evaluated predicate, expert words and the replayed screen moment. They fix it and retry; mastery picks the next case. | `engine/guard.py`, `web/app/teach` |

## How questions are chosen (not a generic LLM follow-up)
1. Each rule has slots with a state: `missing`, `hypothesized` (from transcripts), `expert_stated` (live), `confirmed` (teach-back), `conflicted`.
2. For the screen event that just happened, candidate (rule, slot) pairs are scored by **risk x slot weight x expected uncertainty removed**. The top one is asked; guardrail and escalation slots get a boost until one guardrail question has been asked. (This is risk-weighted uncertainty reduction, not calibrated information gain.)
3. A Socratic ladder climbs per slot: "Why that step?" then "When would you NOT do that?" then "What would make you change that decision?" then "When would you hand this to someone else, and who?"
4. The expert's answer is extracted into slots with a quote and timestamp. "I don't know" is accepted and leaves the slot unresolved.

## The rules (all start as hypotheses; fire in Teach labelled "transcript only" until confirmed live)

| Rule | Fires when (predicate over the form) | Severity | Safe route |
|---|---|---|---|
| R1 Somatic first | refusal AND no pain/physical check logged | blocks Save | log the check, then decide |
| R2 Interaction first | refusal, same carer retrying unchanged, 2+ times | warns | swap carer / psychologist |
| R3 Repeat escalate | 3+ occurrences today AND nothing escalated | blocks Save | team meeting |
| R4 Treatment routing | PRN medication chosen AND not routed to nurse/physician | blocks Save | nurse, then coordinating physician |
| R5 Habitual vs new | escalating without saying new or habitual | warns | classify first |
| R6 Exit-seeking | exit-seeking handled with a refusal strategy | blocks Save | integration plan review |

Each fired rule shows its predicate text and a per-clause match table, so nothing is a hidden trick. Only these 6 are executable. The rules cite 9 of the 77 interview units; every rule card in the Work Map also lists the 3 most related units retrieved from the whole transcript set (labelled automatic, not confirmed), and all 70 gold-eligible units feed the held-out evaluation.

## How abstention and escalation work (and what is honest)
- **Fail closed to a human (live):** `engine/scope.py` is a transparent lexicon (medication, dose, sedative, fall, choking, chest pain, unresponsive, pain, swelling, deterioration, and similar). If the observation text matches and the record is not escalated to a nurse, physician or team meeting, Save is blocked. This is not learned and cannot be talked around.
- **Outside learned knowledge (live):** if the incident type is one no rule covers (for example "Other" or "Medication request" with nothing else firing), Teach abstains: Save is blocked until the record is escalated to a nurse, physician or team meeting. This uses the form's incident type, not semantic understanding of free text.
- **Silence is abstention (live):** the apprentice does not ask when the gate is closed, the event is stale, or no uncertain slot is relevant to the screen event.
- **Missing stays missing (live):** a step with no live explanation says so; events that were demonstrated but never explained are listed, not guessed.
- **Held-out abstention (evaluation only):** `engine/eval_heldout.py` learns from some sessions and tests on unseen ones. It answers when the top retrieval score clears a threshold tuned on the other folds, otherwise it abstains. It is not wired into the live path; live abstention is the incident-type coverage check above plus the scope lexicon, which are coarser and rule-based. A refusal-type case that fires no rule still saves.

## Evidence and honesty
- Seeded knowledge and live capture are different provenance classes; the Map labels each. Dataset summaries are never shown as quotations.
- Confidence is facets (evidence strength, source class, teach-back, open slots), never a probability.
- Held-out results (160 queries, 5 leave-session-group-out folds, LLM-adjudicated labels, not clinician-reviewed): plain TF-IDF Recall@3 0.61, structured Care Map 0.47 (it indexes only the 50 rule-bearing units, so it does not win on recall). What it adds: fail-closed escalation recall 1.0 on clinical queries, 0.74 correct abstention on out-of-knowledge queries, provenance on every answer.
- Extensions kept off the live path: drift detection (`engine/drift.py`), the DP aggregate simulator (`engine/federated.py`; a simulation, not federated learning).

## Run it
See `README.md`. Tests: `engine/.venv/bin/python -m pytest -q engine`; browser: `E2E=1 ... pytest e2e`.
