# Agent Task Instructions (Authoritative)

This repo builds an offline-first D&D 5e SRD SQLite database.

## Non-negotiable Rules

- Do NOT redesign architecture.
- Do NOT introduce new abstractions unless a task explicitly says so.
- Keep tasks small and sequential: one task = one commit/PR.
- All tasks must include tests (offline, mocked; no network).
- All tasks must update verification if they create new data surfaces.
- Idempotency is mandatory: reruns must not create duplicates.

## How to work

For each task:

1) Implement the deliverables.
2) Ensure `pytest` passes.
3) Ensure `python -m dnd_db.cli verify` passes (and task-specific verify if applicable).
4) Add/update README notes if new CLI commands are added.
5) Provide a concise summary + recommended commit message.

## Current Status (Completed)

- Engine + config
- Metadata (Source, ImportRun)
- RawEntity + hash upsert
- REST API client (cached, rate-limited, retry)
- Importers: spells, classes, subclasses, features
- Relationships layer: spell_classes, class_features, subclass_features + loader
- Verification framework + CI/lint/test guardrails
- TASK 1 — Choices v1 (Fighting Style + Generic)
- TASK 2 — Choices v2 (Spell choices, Expertise, Invocations)
- TASK 3 — Prerequisites v1 (As-declared only)
- TASK 4 — Grants/Effects v1 (What features/choices give you)
- TASK 5 — Read Queries Layer (Rules)
- TASK 6 — Character Layer v1 (User state tables)
- TASK 7 — Character Progression Service v1
- TASK 8 — Items/Equipment v1 Importer
- TASK 9 — Conditions v1 Importer
- TASK 10 — Monsters v1 Importer (Optional)
- TASK 11 — Versioning & Change Reports
- TASK 12 — Performance + Index Review

---

### Remaining Tasks (Execute in Order)

## TASK 12 — Performance + Index Review
