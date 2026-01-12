# dnd_db_2

A local, offline-first Dungeons & Dragons 5e SRD database built from the 5e-bits APIs.

## Goal

Import the D&D 5e SRD into a local SQLite database using Python, so that apps
(character sheets, spellbooks, tools) do NOT depend on live internet access.

## Core Principles

- SQLite (local, fast, portable)
- Python-based ETL (extract → transform → load)
- Idempotent imports (safe to re-run)
- Raw JSON preserved alongside normalized tables
- Designed for character-sheet-grade queries

## Planned Components

- `models/` — SQLModel schemas
- `ingest/` — API clients + import pipelines
- `db/` — engine, migrations, helpers
- `data/raw/` — cached API JSON
- `data/sqlite/` — generated database files
- `scripts/` — CLI entry points

## Data Sources

- 5e-bits SRD API
- 5e-bits database schemas (reference only)

## Usage

### Import spells

```bash
python -m dnd_db.cli import-spells
```

### Verification

```bash
python -m dnd_db.cli verify
```

### Tests

```bash
python -m pytest
```

## Idempotent import behavior

An import is idempotent in this repo when running the same importer multiple times
does not create duplicate rows, and only updates rows when the source payload changes.

## Project status

- ✔ spells complete
- ⏳ classes next
- 🔒 schema stable

This project is for personal use only.
