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

---

### Remaining Tasks (Execute in Order)

## TASK 3 — Prerequisites v1 (As-declared only)

Deliverables:

- Add Prerequisite table (applies_to: feature or choice_group)
- Loader reads raw JSON for simple prereqs (level, class/subclass, ability score, feature prereq if present)
- Add CLI: `load-prereqs`, `verify-prereqs`
- Tests: create, rerun, update

Scope:

- Only what’s explicitly present in raw JSON
- No inference engine

---

## TASK 4 — Grants/Effects v1 (What features/choices give you)

Deliverables:

- Add grants tables (minimal): GrantProficiency, GrantSpell, GrantFeature, GrantModifier (optional)
- Loader extracts declared grants from raw JSON where available
- Verification + tests

Scope:

- Represent grants as structured rows, do NOT compute derived stats yet

---

## TASK 5 — Read Queries Layer (Rules)

Deliverables:

- Add query functions under `src/dnd_db/queries/`
- Required queries:
  - features gained by class level
  - spells available by class
  - choices at a given class level
  - granted proficiencies by class level (if grants exist)
- Tests for query outputs

Scope:

- No schema changes
- Read-only

---

## TASK 6 — Character Layer v1 (User state tables)

Deliverables:

- Add character tables (separate module/folder):
  - Character, CharacterLevel, CharacterChoice, CharacterFeature, PreparedSpell/KnownSpell, InventoryItem (optional)
- CLI: `create-character`, `show-character`
- Tests for CRUD basics

Scope:

- Storage only, no rule enforcement

---

## TASK 7 — Character Progression Service v1

Deliverables:

- Implement simple “apply level-up” flow:
  - record level increases
  - record choices
  - validate prereqs (only those represented in Prerequisite table)
- Tests: level up with required choice

Scope:

- Basic validation only
- No full rules engine

---

## TASK 8 — Items/Equipment v1 Importer

Deliverables:

- Normalized item/equipment tables + raw entity
- Importer + verification + tests
- CLI `import-items`

---

## TASK 9 — Conditions v1 Importer

Deliverables:

- Normalized conditions tables + raw entity
- Importer + verification + tests
- CLI `import-conditions`

---

## TASK 10 — Monsters v1 Importer (Optional)

Deliverables:

- Normalized monsters tables + raw entity
- Importer + verification + tests
- CLI `import-monsters`

---

## TASK 11 — Versioning & Change Reports

Deliverables:

- Store import snapshot metadata (run_key, hashes, counts)
- “diff since last run” report command
- Tests

---

## TASK 12 — Performance + Index Review

Deliverables:

- Add/adjust indexes based on query patterns
- Batch insert improvements where needed
- Ensure tests still pass
