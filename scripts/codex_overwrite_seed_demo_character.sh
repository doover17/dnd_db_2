#!/usr/bin/env bash
set -euo pipefail

mkdir -p tools scripts

cat > tools/seed_demo_character.py <<'PY'
#!/usr/bin/env python3
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DEFAULT_DB = Path("./data/sqlite/dnd_rules.db")

def now_iso() -> str:
    # SQLite-friendly ISO timestamp (UTC). Example: 2026-01-13 14:05:33
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

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

def colset(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"pragma table_info({table});").fetchall()}

def get_id_by_name(conn: sqlite3.Connection, table: str, name: str) -> int | None:
    if not table_exists(conn, table):
        return None
    cols = colset(conn, table)
    if not {"id", "name"}.issubset(cols):
        return None
    row = conn.execute(
        f"select id from {table} where lower(name)=lower(?) limit 1;",
        (name,),
    ).fetchone()
    return int(row["id"]) if row else None

def insert_character(conn: sqlite3.Connection, name: str) -> int:
    cols = colset(conn, "characters")

    # If already exists, return it
    if "name" in cols:
        existing = conn.execute(
            "select id from characters where lower(name)=lower(?) limit 1;",
            (name,),
        ).fetchone()
        if existing:
            return int(existing["id"])

    fields: list[str] = []
    values: list[object] = []

    if "name" in cols:
        fields.append("name")
        values.append(name)

    ts = now_iso()
    if "created_at" in cols:
        fields.append("created_at")
        values.append(ts)
    if "updated_at" in cols:
        fields.append("updated_at")
        values.append(ts)

    if fields:
        placeholders = ", ".join(["?"] * len(fields))
        q = f"insert into characters ({', '.join(fields)}) values ({placeholders});"
        conn.execute(q, values)
    else:
        # ultra-minimal schema: rely on defaults
        conn.execute("insert into characters default values;")

    return int(conn.execute("select last_insert_rowid();").fetchone()[0])

def ensure_level_row(conn: sqlite3.Connection, character_id: int, class_name: str, level: int) -> None:
    if not table_exists(conn, "character_levels"):
        return
    lvl_cols = colset(conn, "character_levels")

    class_id = get_id_by_name(conn, "classes", class_name)
    if class_id is None:
        print(f"Could not find class {class_name!r}; skipping character_levels.")
        return

    already = conn.execute(
        "select 1 from character_levels where character_id=? and class_id=? limit 1;",
        (character_id, class_id),
    ).fetchone()
    if already:
        return

    insert_cols = ["character_id", "class_id", "level"]
    insert_vals: list[object] = [character_id, class_id, level]

    # Optional subclass_id column
    if "subclass_id" in lvl_cols:
        insert_cols.insert(2, "subclass_id")
        insert_vals.insert(2, None)

    # Optional timestamps
    ts = now_iso()
    if "created_at" in lvl_cols:
        insert_cols.append("created_at")
        insert_vals.append(ts)
    if "updated_at" in lvl_cols:
        insert_cols.append("updated_at")
        insert_vals.append(ts)

    q = f"insert into character_levels ({', '.join(insert_cols)}) values ({', '.join(['?']*len(insert_cols))});"
    conn.execute(q, insert_vals)

def seed_spells(conn: sqlite3.Connection, character_id: int, table: str, spell_names: list[str]) -> None:
    if not table_exists(conn, table):
        return
    tcols = colset(conn, table)
    if not {"character_id", "spell_id"}.issubset(tcols):
        return

    ts = now_iso()
    for sname in spell_names:
        sid = get_id_by_name(conn, "spells", sname)
        if not sid:
            continue

        exists = conn.execute(
            f"select 1 from {table} where character_id=? and spell_id=? limit 1;",
            (character_id, sid),
        ).fetchone()
        if exists:
            continue

        cols = ["character_id", "spell_id"]
        vals: list[object] = [character_id, sid]

        if "created_at" in tcols:
            cols.append("created_at")
            vals.append(ts)
        if "updated_at" in tcols:
            cols.append("updated_at")
            vals.append(ts)

        q = f"insert into {table} ({', '.join(cols)}) values ({', '.join(['?']*len(cols))});"
        conn.execute(q, vals)

def main() -> None:
    p = db_path()
    if not p.exists():
        raise SystemExit(f"DB not found: {p}")

    with connect(p) as conn:
        if not table_exists(conn, "characters"):
            raise SystemExit("No characters table found.")

        cid = insert_character(conn, "Demo Wizard")
        print(f"Demo Wizard id={cid}")

        ensure_level_row(conn, cid, "Wizard", 2)

        seed_list = ["Magic Missile", "Shield", "Mage Armor"]
        seed_spells(conn, cid, "character_known_spells", seed_list)
        seed_spells(conn, cid, "character_prepared_spells", seed_list)

        conn.commit()
        print("Done.")

if __name__ == "__main__":
    main()
PY

chmod +x tools/seed_demo_character.py
echo "==> Overwrote tools/seed_demo_character.py with NOT NULL-safe timestamps."
echo "Run:"
echo "  python tools/seed_demo_character.py"
echo "  python tools/character_sheet_preview.py"
