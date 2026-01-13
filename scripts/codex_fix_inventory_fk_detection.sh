#!/usr/bin/env bash
set -euo pipefail

# Overwrite list_inventory.py and seed_starting_equipment.py with FK auto-detect

cat > tools/_inv_fk.py <<'PY'
#!/usr/bin/env python3
from __future__ import annotations

import sqlite3

def inventory_item_fk_column(conn: sqlite3.Connection) -> str:
    """
    Return the column in inventory_items that references items.* via FK.
    Raises if not found.
    """
    fks = conn.execute("pragma foreign_key_list(inventory_items);").fetchall()
    for fk in fks:
        if fk["table"] == "items":
            return fk["from"]
    # Fallback heuristic: pick the only non-character *_id column
    cols = [r["name"] for r in conn.execute("pragma table_info(inventory_items);").fetchall()]
    candidates = [c for c in cols if c.endswith("_id") and c not in ("character_id",)]
    if len(candidates) == 1:
        return candidates[0]
    raise RuntimeError(f"Could not detect inventory_items -> items FK column. Columns={cols}, fks={[dict(x) for x in fks]}")
PY

cat > tools/list_inventory.py <<'PY'
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

from tools._inv_fk import inventory_item_fk_column

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
    ap = argparse.ArgumentParser(description="List a character's inventory items.")
    ap.add_argument("--character-id", type=int, required=True)
    args = ap.parse_args()

    p = db_path()
    if not p.exists():
        raise SystemExit(f"DB not found: {p}")

    with connect(p) as conn:
        inv_cols = colset(conn, "inventory_items")
        qty_col = "quantity" if "quantity" in inv_cols else None
        item_fk = inventory_item_fk_column(conn)

        q = f"""
        select i.name as item_name{", ii." + qty_col + " as qty" if qty_col else ""}
        from inventory_items ii
        join items i on i.id = ii.{item_fk}
        where ii.character_id=?
        order by i.name;
        """
        rows = conn.execute(q, (args.character_id,)).fetchall()
        if not rows:
            print("(inventory empty)")
            return

        for r in rows:
            if qty_col:
                print(f"- {r['item_name']} x{int(r['qty'])}")
            else:
                print(f"- {r['item_name']}")

if __name__ == "__main__":
    main()
PY

cat > tools/seed_starting_equipment.py <<'PY'
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from tools._inv_fk import inventory_item_fk_column

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

def find_item_id(conn: sqlite3.Connection, name: str) -> int | None:
    r = conn.execute("select id from items where lower(name)=lower(?) limit 1;", (name,)).fetchone()
    if r:
        return int(r["id"])
    r = conn.execute("select id from items where lower(name) like lower(?) order by name limit 1;", (f"%{name}%",)).fetchone()
    if r:
        return int(r["id"])
    return None

def upsert_inventory(conn: sqlite3.Connection, character_id: int, item_fk_col: str, item_id: int, qty: int) -> tuple[str, int]:
    cols = colset(conn, "inventory_items")
    ts = now_iso()
    has_qty = "quantity" in cols

    existing = conn.execute(
        f"select * from inventory_items where character_id=? and {item_fk_col}=? limit 1;",
        (character_id, item_id),
    ).fetchone()

    if existing:
        if has_qty:
            new_qty = int(existing["quantity"]) + qty
            updates = ["quantity=?"]
            params: list[object] = [new_qty]
            if "updated_at" in cols:
                updates.append("updated_at=?")
                params.append(ts)
            params += [character_id, item_id]
            conn.execute(
                f"update inventory_items set {', '.join(updates)} where character_id=? and {item_fk_col}=?;",
                params,
            )
            return ("updated", new_qty)
        return ("exists", 1)

    insert_cols = ["character_id", item_fk_col]
    insert_vals: list[object] = [character_id, item_id]
    if has_qty:
        insert_cols.append("quantity")
        insert_vals.append(qty)
    if "created_at" in cols:
        insert_cols.append("created_at")
        insert_vals.append(ts)
    if "updated_at" in cols:
        insert_cols.append("updated_at")
        insert_vals.append(ts)

    q = f"insert into inventory_items ({', '.join(insert_cols)}) values ({', '.join(['?']*len(insert_cols))});"
    conn.execute(q, insert_vals)
    return ("inserted", qty)

def main() -> None:
    ap = argparse.ArgumentParser(description="Seed inventory_items from classes.starting_equipment JSON for a character.")
    ap.add_argument("--character-id", type=int, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    p = db_path()
    if not p.exists():
        raise SystemExit(f"DB not found: {p}")

    with connect(p) as conn:
        if not conn.execute("select 1 from characters where id=?;", (args.character_id,)).fetchone():
            raise SystemExit(f"Character not found: id={args.character_id}")

        item_fk_col = inventory_item_fk_column(conn)

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

        total_inserted = 0
        total_updated = 0
        missing: list[str] = []

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

                item_id = find_item_id(conn, str(equip_name))
                if item_id is None:
                    missing.append(str(equip_name))
                    print(f" - MISSING item: {equip_name} x{qty}")
                    continue

                if args.dry_run:
                    print(f" - would add: {equip_name} x{qty}")
                    continue

                status, new_qty = upsert_inventory(conn, args.character_id, item_fk_col, item_id, qty)
                if status == "inserted":
                    total_inserted += 1
                    print(f" - inserted: {equip_name} x{qty}")
                elif status == "updated":
                    total_updated += 1
                    print(f" - updated: {equip_name} -> quantity {new_qty}")
                else:
                    print(f" - exists: {equip_name}")

        if args.dry_run:
            print("\nDRY RUN complete.")
            if missing:
                print("Missing items:", ", ".join(sorted(set(missing))))
            return

        conn.commit()
        print(f"\nSeed complete. inserted rows: {total_inserted} | updated rows: {total_updated}")
        if missing:
            print("Missing items:", ", ".join(sorted(set(missing))))

if __name__ == "__main__":
    main()
PY

chmod +x tools/list_inventory.py tools/seed_starting_equipment.py
echo "==> Fixed inventory scripts to detect the FK column dynamically."
