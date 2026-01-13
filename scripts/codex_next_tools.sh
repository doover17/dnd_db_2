#!/usr/bin/env bash
set -euo pipefail

mkdir -p tools scripts

cat > tools/db_health_report.py <<'PY'
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
PY

cat > tools/character_sheet_preview.py <<'PY'
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

PY

chmod +x tools/db_health_report.py tools/character_sheet_preview.py
chmod +x scripts/codex_next_tools.sh

echo "==> Added:"
echo "  tools/db_health_report.py"
echo "  tools/character_sheet_preview.py"
echo ""
echo "Run:"
echo "  python tools/db_health_report.py"
echo "  python tools/character_sheet_preview.py"
