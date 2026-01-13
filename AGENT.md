# AGENT.md

You are an AI coding agent working in this repository.

## How to proceed
1. Open `AGENT_TASKS.md`.
2. Identify the **next incomplete TASK**.
3. Complete **only that task**.
4. Do not work ahead.
5. Stop when the task’s Definition of Done is met.

## Required checks before stopping
- `pytest` passes
- `python -m dnd_db.cli verify` passes
- Any task-specific verify command passes

## Output expectations
When finished, report:
- What you implemented
- What files changed
- Any risks or gaps noticed (do NOT fix them unless instructed)
- A recommended git commit message

If instructions conflict:
- `AGENT_TASKS.md` > `CONTRIBUTING_AGENT.md` > README > code comments