# dnd_db_2

A local, offline-first Dungeons & Dragons 5e SRD database built from the 5e-bits APIs.
The project downloads SRD content, stores the raw JSON, and normalizes it into
SQLite tables for fast, repeatable queries.

## What this app does

- Imports SRD data into SQLite with idempotent loaders.
- Preserves raw JSON alongside normalized tables for traceability.
- Provides CLI commands for importing, verifying, and reporting changes.
- Supports lightweight character storage and choice/grant/prereq surfaces.

## Data sources

- 5e-bits SRD API
- 5e-bits database schemas (reference only)

## Project layout

- `src/dnd_db/models/` - SQLModel schemas
- `src/dnd_db/ingest/` - API clients + import pipelines
- `src/dnd_db/db/` - engine + helpers
- `src/dnd_db/verify/` - verification checks
- `src/dnd_db/queries/` - read-only query helpers
- `data/raw/` - cached API JSON
- `data/sqlite/` - generated SQLite databases

## Setup

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
```

## Quickstart

1) Import core data (example: spells):

```bash
python -m dnd_db.cli import-spells
```

2) Run verification:

```bash
python -m dnd_db.cli verify
```

3) Load derived layers (choices, prereqs, grants) as needed:

```bash
python -m dnd_db.cli load-choices
python -m dnd_db.cli load-prereqs
python -m dnd_db.cli load-grants
```

## CLI commands

### Importers

```bash
python -m dnd_db.cli import-spells
python -m dnd_db.cli import-classes
python -m dnd_db.cli import-subclasses
python -m dnd_db.cli import-features
python -m dnd_db.cli import-items
python -m dnd_db.cli import-conditions
python -m dnd_db.cli import-monsters
```

### Loaders

```bash
python -m dnd_db.cli load-relationships
python -m dnd_db.cli load-choices
python -m dnd_db.cli load-prereqs
python -m dnd_db.cli load-grants
```

### Verification

```bash
python -m dnd_db.cli verify
python -m dnd_db.cli verify-choices
python -m dnd_db.cli verify-prereqs
python -m dnd_db.cli verify-grants
python -m dnd_db.cli verify-items
python -m dnd_db.cli verify-conditions
python -m dnd_db.cli verify-monsters
```

### Reporting

```bash
python -m dnd_db.cli report-changes
```

### Character storage

```bash
python -m dnd_db.cli create-character --name "Elandra" --class-id 1 --level 1
python -m dnd_db.cli show-character --id 1
```

### Tests

```bash
python -m pytest
```

## Notes on idempotency

Imports are safe to re-run. If the source payload changes, the normalized row
is updated; otherwise it is left untouched. This keeps the database consistent
across repeated runs.

## Change reports

The `report-changes` command records a snapshot of table counts and content hashes,
then compares it to the previous snapshot. This helps you detect data drift between
imports without diffing the entire database.

## License

This project is for personal use only.
