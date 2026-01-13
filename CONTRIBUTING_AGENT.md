# CONTRIBUTING_AGENT.md

These rules exist to keep the database stable and predictable.

## Absolute Rules
- Do NOT redesign schemas unless a task explicitly says so.
- Do NOT refactor unrelated code.
- Do NOT introduce generic abstractions “for later.”
- Do NOT remove fields, tables, or constraints.
- Do NOT hit the network in tests.

## Scope Control
- One task = one commit.
- If something feels useful but is not requested, write it down and STOP.
- Prefer explicit, boring code over clever code.

## Data Integrity
- All loaders must be idempotent.
- Unique constraints must enforce no duplicates.
- Raw JSON must remain canonical and untouched.
- Derived tables must be reproducible from raw JSON.

## Tests
- All new behavior requires tests.
- Tests must be deterministic and offline.
- Failing verification is a hard failure.

## Style
- Match existing patterns.
- Keep functions small.
- Favor clarity over DRY.

## When in doubt
Stop and report uncertainty instead of guessing.