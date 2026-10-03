# Alzheimers-Cure: Apprentice (Hack-Nation 7 x ElevenLabs, Challenge 01)

Apprentice captures how an expert documents and escalates a dementia-care refusal incident on a fake care-records screen, turns it into an inspectable Work Map with guardrails and provenance, and teaches a new caregiver on an unseen case. Training and documentation support only; not diagnosis or treatment.

Capture -> Debrief -> Map -> Teach. Voice (ElevenAgents) is an adapter on top of an offline-first engine.

## Run
```bash
python3 -m venv engine/.venv && engine/.venv/bin/pip install -r engine/requirements.txt
cp .env.example .env            # fill keys; never commit
engine/.venv/bin/uvicorn engine.api:app --port 8000
cd web && npm install && npm run dev      # http://localhost:3000 (web/.env.local needs the ElevenLabs vars)
```
Tests: `engine/.venv/bin/python -m pytest -q engine`; browser: `E2E=1 engine/.venv/bin/python -m pytest e2e -q` (engine with `APPRENTICE_OFFLINE=1 APPRENTICE_COOLDOWN=2`).
Data: place `dementia_care_knowledge_deidentified.json` in `data/` (git-ignored, proprietary).
