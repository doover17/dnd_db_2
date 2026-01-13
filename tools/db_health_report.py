#!/usr/bin/env python3
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DEFAULT_DB = Path("./data/sqlite/dnd_rules.db")

CORE_TABLES = [
    "sources", "importrun", "import_snapshots",
    "raw_entities",
    "spells", "items", "classes", "subclasses", "features", "monsters", "conditions",
    "spell_classes", "class_features", "subclass_features",
    "prerequisites",
    "grant_features", "grant_spells", "grant_proficiencies",
]

def db_path() -> Path:
    return Path(os.environ.get("DND_DB_PATH", str(DEFAULT_DB))).expanduser().resolve()

def connect(p: Path) -> sqlite3.Connection:
    c = sqlite3.connect(str(p))
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON;")
    return c

def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "select 1 from sqlite_master where type='table' and name=?;", (name,)
    ).fetchone() is not None

def count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"select count(*) from {table};").fetchone()[0])

def cols(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r["name"] for r in conn.execute(f"pragma table_info({table});").fetchall()]

def print_recent_run(conn: sqlite3.Connection) -> None:
    if not table_exists(conn, "importrun"):
        print("\nNo importrun table found.")
        return

    c = set(cols(conn, "importrun"))
    # Find plausible time column
    time_col = None
    for cand in ["started_at", "created_at", "run_at", "timestamp", "ts"]:
        if cand in c:
            time_col = cand
            break

    # Find plausible id column
    id_col = "id" if "id" in c else None

    if not id_col:
        print("\nimportrun exists, but no id column found.")
        return

    order = time_col if time_col else id_col
    row = conn.execute(f"select * from importrun order by {order} desc limit 1;").fetchone()
    if not row:
        print("\nNo rows in importrun yet.")
        return

    print("\nMost recent import run:")
    # Print a few helpful columns if they exist
    for k in ["id", time_col, "status", "note", "source_id", "api_base_url", "data_hash"]:
        if k and k in row.keys():
            print(f"  {k}: {row[k]}")

def main() -> None:
    p = db_path()
    if not p.exists():
        raise SystemExit(f"DB not found: {p}")

    with connect(p) as conn:
        print(f"DB: {p}")

        # Core counts
        print("\nCore table counts:")
        for t in CORE_TABLES:
            if table_exists(conn, t):
                print(f"  {t:<20} {count(conn, t)}")

        # Relationship density (helps decide “what’s next”)
        rels = [
            ("spell_classes", "spells", "classes"),
            ("class_features", "classes", "features"),
            ("subclass_features", "subclasses", "features"),
            ("prerequisites", None, None),
            ("grant_spells", None, None),
            ("grant_features", None, None),
        ]
        print("\nRelationship highlights:")
        for jt, a, b in rels:
            if not table_exists(conn, jt):
                continue
            n = count(conn, jt)
            msg = f"  {jt:<20} {n}"
            if a and table_exists(conn, a):
                msg += f" | {a}={count(conn,a)}"
            if b and table_exists(conn, b):
                msg += f" | {b}={count(conn,b)}"
            print(msg)

        print_recent_run(conn)

if __name__ == "__main__":
    main()
