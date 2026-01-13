#!/usr/bin/env python3
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DEFAULT_DB = Path("./data/sqlite/dnd_rules.db")

def db_path() -> Path:
    return Path(os.environ.get("DND_DB_PATH", str(DEFAULT_DB))).expanduser().resolve()

def connect(p: Path) -> sqlite3.Connection:
    c = sqlite3.connect(str(p))
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON;")
    return c

def main() -> None:
    p = db_path()
    if not p.exists():
        raise SystemExit(f"DB not found: {p}")

    with connect(p) as conn:
        print("inventory_items columns:")
        cols = conn.execute("pragma table_info(inventory_items);").fetchall()
        for c in cols:
            print(f" - {c['name']:<22} {c['type'] or ''}{' (PK)' if c['pk'] else ''}")

        print("\ninventory_items foreign keys:")
        fks = conn.execute("pragma foreign_key_list(inventory_items);").fetchall()
        if not fks:
            print(" (none)")
        else:
            for fk in fks:
                # columns: id, seq, table, from, to, on_update, on_delete, match
                print(f" - from {fk['from']} -> {fk['table']}.{fk['to']} (on_delete={fk['on_delete']})")

        # show a couple rows if any
        n = conn.execute("select count(*) as n from inventory_items;").fetchone()["n"]
        print(f"\nrow count: {n}")
        if n:
            rows = conn.execute("select * from inventory_items limit 5;").fetchall()
            print("\nsample rows (up to 5):")
            for r in rows:
                print(dict(r))

if __name__ == "__main__":
    main()
