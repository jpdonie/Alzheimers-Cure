# Project instructions

Read [docs/PROJECT.md](docs/PROJECT.md) before planning or changing code. Its linked files are required, not optional background.

## Single-source rule

- Never create `V1`, `V2`, `final`, `new`, `old`, `min`, or similarly suffixed planning documents.
- Update the canonical document in place and use Git history. Do not duplicate it for versioning.
- Do not create a second roadmap, requirements list, architecture plan, or UI prompt.
- If two documents conflict, consolidate them into the canonical file named in `docs/PROJECT.md` before implementation.
- Keep status in `docs/DELIVERY.md`; do not encode status by duplicating files.

## Working rule

Implement the smallest vertical slice that advances the live Capture -> Debrief -> Map -> Teach path. Keep each change focused, tested, reviewable, and runnable. Do not broaden clinical claims or move pitch-only features onto the live demo path.

## Code rule

- Never create implementation names such as `v1`, `v2`, `new`, `old`, `final`, `fixed`, `copy`, or `legacy` to avoid improving the existing design.
- Refactor the canonical implementation in place behind tests. Migrate callers, then delete superseded code.
- One concept has one clear owner. Do not maintain competing services, components, schemas, state machines, or utility modules.
- Use small cohesive modules, explicit typed interfaces, dependency injection at provider boundaries, and pure domain logic where practical.
- Do not add abstractions, factories, wrappers, or dependencies without a concrete current need.
