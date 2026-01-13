#!/usr/bin/env python3
from __future__ import annotations

import argparse
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

def colset(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"pragma table_info({table});").fetchall()}

def main() -> None:
    ap = argparse.ArgumentParser(description="List a character's inventory items (freeform).")
    ap.add_argument("--character-id", type=int, required=True)
    args = ap.parse_args()

    p = db_path()
    if not p.exists():
        raise SystemExit(f"DB not found: {p}")

    with connect(p) as conn:
        cols = colset(conn, "inventory_items")
        has_qty = "quantity" in cols
        has_notes = "notes" in cols

        rows = conn.execute(
            "select * from inventory_items where character_id=? order by lower(name);",
            (args.character_id,),
        ).fetchall()

        if not rows:
            print("(inventory empty)")
            return

        for r in rows:
            name = r["name"]
            qty = int(r["quantity"]) if has_qty and r["quantity"] is not None else 1
            line = f"- {name}"
            if has_qty:
                line += f" x{qty}"
            if has_notes and r["notes"]:
                line += f"  [{r['notes']}]"
            print(line)

if __name__ == "__main__":
    main()
