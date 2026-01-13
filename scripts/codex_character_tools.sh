#!/usr/bin/env bash
set -euo pipefail

mkdir -p scripts tools

# 1) Patch tools/character_sheet_preview.py to actually run main()
python - <<'PY'
from pathlib import Path

p = Path("tools/character_sheet_preview.py")
txt = p.read_text(encoding="utf-8")

if 'if __name__ == "__main__"' not in txt:
    txt = txt.rstrip() + """

if __name__ == "__main__":
    main()
"""
    p.write_text(txt, encoding="utf-8")
    print("Patched tools/character_sheet_preview.py (added main() entrypoint).")
else:
    print("tools/character_sheet_preview.py already has an entrypoint.")
PY

# 2) Add a tiny seeder: creates a demo character + a level row (and optionally known/prepared spells)
cat > tools/seed_demo_character.py <<'PY'
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

def colset(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"pragma table_info({table});").fetchall()}

def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("select 1 from sqlite_master where type='table' and name=?;", (name,)).fetchone() is not None

def get_id_by_name(conn: sqlite3.Connection, table: str, name: str) -> int | None:
    if not table_exists(conn, table):
        return None
    cols = colset(conn, table)
    if "id" not in cols or "name" not in cols:
        return None
    row = conn.execute(f"select id from {table} where lower(name)=lower(?) limit 1;", (name,)).fetchone()
    return int(row["id"]) if row else None

def main() -> None:
    p = db_path()
    if not p.exists():
        raise SystemExit(f"DB not found: {p}")

    with connect(p) as conn:
        # 1) Create character row (minimal, adaptive to columns)
        if not table_exists(conn, "characters"):
            raise SystemExit("No characters table found.")

        ccols = colset(conn, "characters")
        fields = []
        vals = []

        # set name if present
        if "name" in ccols:
            fields.append("name")
            vals.append("Demo Wizard")

        # set created_at/updated_at if present (optional)
        for ts in ["created_at", "updated_at"]:
            if ts in ccols:
                fields.append(ts)
                vals.append(None)  # let DB default if any; otherwise NULL is fine for a demo

        # Check if demo already exists
        if "name" in ccols:
            existing = conn.execute("select id from characters where lower(name)=lower(?) limit 1;", ("Demo Wizard",)).fetchone()
            if existing:
                cid = int(existing["id"])
                print(f"Demo character already exists: id={cid}")
            else:
                q = f"insert into characters ({', '.join(fields)}) values ({', '.join(['?']*len(fields))});"
                conn.execute(q, vals)
                cid = int(conn.execute("select last_insert_rowid();").fetchone()[0])
                print(f"Created demo character: id={cid}")
        else:
            # If no name column, just insert default row
            conn.execute("insert into characters default values;")
            cid = int(conn.execute("select last_insert_rowid();").fetchone()[0])
            print(f"Created demo character (no name col): id={cid}")

        # 2) Add a level row (Wizard 2) if character_levels exists
        if table_exists(conn, "character_levels"):
            lvl_cols = colset(conn, "character_levels")
            class_id = get_id_by_name(conn, "classes", "Wizard")
            if class_id is None:
                print("Could not find Wizard class_id; skipping character_levels.")
            else:
                # Avoid duplicates
                already = conn.execute(
                    "select 1 from character_levels where character_id=? and class_id=? limit 1;",
                    (cid, class_id),
                ).fetchone()
                if already:
                    print("character_levels row already exists for Demo Wizard.")
                else:
                    insert_cols = ["character_id", "class_id", "level"]
                    insert_vals = [cid, class_id, 2]
                    if "subclass_id" in lvl_cols:
                        insert_cols.insert(2, "subclass_id")
                        insert_vals.insert(2, None)
                    q = f"insert into character_levels ({', '.join(insert_cols)}) values ({', '.join(['?']*len(insert_cols))});"
                    conn.execute(q, insert_vals)
                    print("Added character_levels: Wizard 2")

        # 3) Optionally add a couple known/prepared spells if tables exist
        spell_ids = {}
        for s in ["Magic Missile", "Shield", "Mage Armor"]:
            sid = get_id_by_name(conn, "spells", s)
            if sid:
                spell_ids[s] = sid

        def maybe_insert_spells(table: str) -> None:
            if not table_exists(conn, table):
                return
            tcols = colset(conn, table)
            if not {"character_id", "spell_id"}.issubset(tcols):
                return
            for sname, sid in spell_ids.items():
                exists = conn.execute(
                    f"select 1 from {table} where character_id=? and spell_id=? limit 1;",
                    (cid, sid),
                ).fetchone()
                if not exists:
                    conn.execute(f"insert into {table} (character_id, spell_id) values (?, ?);", (cid, sid))
            print(f"Seeded {table}: {len(spell_ids)} spells (if they existed)")

        maybe_insert_spells("character_known_spells")
        maybe_insert_spells("character_prepared_spells")

        conn.commit()
        print("Done.")

if __name__ == "__main__":
    main()
PY

chmod +x tools/seed_demo_character.py
echo "==> Done. Next run:"
echo "  python tools/character_sheet_preview.py"
echo "  python tools/seed_demo_character.py"
echo "  python tools/character_sheet_preview.py"
