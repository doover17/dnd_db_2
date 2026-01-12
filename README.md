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

This project is for personal use only.
