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

def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "select 1 from sqlite_master where type='table' and name=?;", (name,)
    ).fetchone() is not None

def count_where(conn: sqlite3.Connection, table: str, where: str, params=()) -> int:
    return int(conn.execute(f"select count(*) from {table} where {where};", params).fetchone()[0])

def main() -> None:
    p = db_path()
    if not p.exists():
        raise SystemExit(f"DB not found: {p}")

    with connect(p) as conn:
        if not table_exists(conn, "characters"):
            raise SystemExit("No characters table found.")

        chars = conn.execute("select * from characters order by id limit 10;").fetchall()
        if not chars:
            print("No characters found yet.")
            print("Next step is either:")
            print("  1) add a tiny 'create character' CLI path, or")
            print("  2) add a seed tool to insert a demo character.")
            return

        # Show a compact preview per character
        print(f"Found {len(chars)} character(s) (showing up to 10):")
        for ch in chars:
            cid = ch["id"] if "id" in ch.keys() else None
            name = ch["name"] if "name" in ch.keys() else f"character_{cid}"

            print(f"\n== {name} (id={cid}) ==")

            # Levels
            if cid and table_exists(conn, "character_levels"):
                lvl_rows = conn.execute(
                    "select class_id, subclass_id, level from character_levels where character_id=? order by level;",
                    (cid,),
                ).fetchall()
                if lvl_rows:
                    total_level = sum(int(r["level"]) for r in lvl_rows if r["level"] is not None)
                    print(f"Levels rows: {len(lvl_rows)} | total levels (sum of rows): {total_level}")
                else:
                    print("Levels: none")

            # Spells (known/prepared)
            if cid and table_exists(conn, "character_known_spells"):
                n = count_where(conn, "character_known_spells", "character_id=?", (cid,))
                print(f"Known spells: {n}")
            if cid and table_exists(conn, "character_prepared_spells"):
                n = count_where(conn, "character_prepared_spells", "character_id=?", (cid,))
                print(f"Prepared spells: {n}")

            # Inventory
            if cid and table_exists(conn, "inventory_items"):
                n = count_where(conn, "inventory_items", "character_id=?", (cid,))
                print(f"Inventory items: {n}")

            # Features
            if cid and table_exists(conn, "character_features"):
                n = count_where(conn, "character_features", "character_id=?", (cid,))
                print(f"Character features: {n}")

if __name__ == "__main__":
    main()
