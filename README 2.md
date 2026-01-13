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

### Import items

```bash
python -m dnd_db.cli import-items
```

### Import conditions

```bash
python -m dnd_db.cli import-conditions
```

### Import monsters

```bash
python -m dnd_db.cli import-monsters
```

### Verification

```bash
python -m dnd_db.cli verify
```

### Load prerequisites

```bash
python -m dnd_db.cli load-prereqs
```

### Verify prerequisites

```bash
python -m dnd_db.cli verify-prereqs
```

### Load grants

```bash
python -m dnd_db.cli load-grants
```

### Verify grants

```bash
python -m dnd_db.cli verify-grants
```

### Verify items

```bash
python -m dnd_db.cli verify-items
```

### Verify conditions

```bash
python -m dnd_db.cli verify-conditions
```

### Verify monsters

```bash
python -m dnd_db.cli verify-monsters
```

### Report changes since last snapshot

```bash
python -m dnd_db.cli report-changes
```

### Create a character

```bash
python -m dnd_db.cli create-character --name "Elandra" --class-id 1 --level 1
```

### Show a character

```bash
python -m dnd_db.cli show-character --id 1
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
