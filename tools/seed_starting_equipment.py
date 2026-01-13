#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DEFAULT_DB = Path("./data/sqlite/dnd_rules.db")

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def db_path() -> Path:
    return Path(os.environ.get("DND_DB_PATH", str(DEFAULT_DB))).expanduser().resolve()

def connect(p: Path) -> sqlite3.Connection:
    c = sqlite3.connect(str(p))
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON;")
    return c

def colset(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"pragma table_info({table});").fetchall()}

def inventory_has(conn: sqlite3.Connection, character_id: int, name: str) -> sqlite3.Row | None:
    return conn.execute(
        "select * from inventory_items where character_id=? and lower(name)=lower(?) limit 1;",
        (character_id, name),
    ).fetchone()

def insert_inventory(conn: sqlite3.Connection, character_id: int, name: str, qty: int, notes: str | None) -> None:
    cols = colset(conn, "inventory_items")
    ts = now_iso()

    insert_cols = ["character_id", "name"]
    insert_vals: list[object] = [character_id, name]

    if "quantity" in cols:
        insert_cols.append("quantity")
        insert_vals.append(qty)
    if "notes" in cols and notes:
        insert_cols.append("notes")
        insert_vals.append(notes)
    if "created_at" in cols:
        insert_cols.append("created_at")
        insert_vals.append(ts)

    q = f"insert into inventory_items ({', '.join(insert_cols)}) values ({', '.join(['?']*len(insert_cols))});"
    conn.execute(q, insert_vals)

def update_quantity(conn: sqlite3.Connection, row_id: int, new_qty: int) -> None:
    conn.execute("update inventory_items set quantity=? where id=?;", (new_qty, row_id))

def main() -> None:
    ap = argparse.ArgumentParser(description="Seed inventory_items from classes.starting_equipment JSON for a character (freeform name/qty).")
    ap.add_argument("--character-id", type=int, required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--note-prefix", default="Starting equipment", help="Prefix used when writing notes")
    args = ap.parse_args()

    p = db_path()
    if not p.exists():
        raise SystemExit(f"DB not found: {p}")

    with connect(p) as conn:
        if not conn.execute("select 1 from characters where id=?;", (args.character_id,)).fetchone():
            raise SystemExit(f"Character not found: id={args.character_id}")

        inv_cols = colset(conn, "inventory_items")
        if "name" not in inv_cols:
            raise SystemExit("inventory_items must have a 'name' column for this tool.")
        has_qty = "quantity" in inv_cols
        has_notes = "notes" in inv_cols

        lvl_rows = conn.execute(
            """
            select c.name as class_name, c.starting_equipment
            from character_levels cl
            join classes c on c.id = cl.class_id
            where cl.character_id=?
            order by c.name;
            """,
            (args.character_id,),
        ).fetchall()

        if not lvl_rows:
            print("No character_levels rows found. Nothing to seed.")
            return

        inserted = 0
        updated = 0

        for r in lvl_rows:
            class_name = r["class_name"]
            raw = r["starting_equipment"]
            if not raw:
                print(f"[{class_name}] starting_equipment: (empty)")
                continue

            payload = json.loads(raw)
            if not isinstance(payload, list):
                print(f"[{class_name}] starting_equipment JSON is not a list.")
                continue

            print(f"\n[{class_name}] starting equipment entries: {len(payload)}")

            for entry in payload:
                if not isinstance(entry, dict):
                    continue
                equip_name = entry.get("equipment") or entry.get("name")
                qty = int(entry.get("quantity", 1))
                if not equip_name:
                    continue

                notes = None
                if has_notes:
                    notes = f"{args.note_prefix} ({class_name})"

                existing = inventory_has(conn, args.character_id, str(equip_name))
                if existing:
                    if has_qty:
                        new_qty = int(existing["quantity"] or 0) + qty
                        if args.dry_run:
                            print(f" - would update: {equip_name} -> quantity {new_qty}")
                        else:
                            update_quantity(conn, int(existing["id"]), new_qty)
                            print(f" - updated: {equip_name} -> quantity {new_qty}")
                            updated += 1
                    else:
                        print(f" - exists: {equip_name}")
                    continue

                if args.dry_run:
                    print(f" - would insert: {equip_name} x{qty}")
                else:
                    insert_inventory(conn, args.character_id, str(equip_name), qty, notes)
                    print(f" - inserted: {equip_name} x{qty}")
                    inserted += 1

        if args.dry_run:
            print(f"\nDRY RUN complete. would insert={inserted} would update={updated}")
            return

        conn.commit()
        print(f"\nSeed complete. inserted={inserted} updated={updated}")

if __name__ == "__main__":
    main()
