#!/usr/bin/env bash
set -euo pipefail

mkdir -p tools scripts

cat > tools/apply_subclass_features.py <<'PY'
#!/usr/bin/env python3
from __future__ import annotations

import argparse
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

def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("select 1 from sqlite_master where type='table' and name=?;", (name,)).fetchone() is not None

def colset(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"pragma table_info({table});").fetchall()}

def character_exists(conn: sqlite3.Connection, cid: int) -> bool:
    return conn.execute("select 1 from characters where id=? limit 1;", (cid,)).fetchone() is not None

def get_class_id(conn: sqlite3.Connection, class_name: str) -> int:
    row = conn.execute("select id from classes where lower(name)=lower(?) limit 1;", (class_name,)).fetchone()
    if not row:
        raise SystemExit(f"Class not found: {class_name!r}")
    return int(row["id"])

def find_subclass_id(conn: sqlite3.Connection, class_id: int, subclass_name: str) -> int:
    # Try exact match first
    row = conn.execute(
        "select id from subclasses where class_id=? and lower(name)=lower(?) limit 1;",
        (class_id, subclass_name),
    ).fetchone()
    if row:
        return int(row["id"])

    # Fallback: contains match (helps if naming differs slightly)
    row = conn.execute(
        "select id, name from subclasses where class_id=? and lower(name) like lower(?) order by name limit 1;",
        (class_id, f"%{subclass_name}%"),
    ).fetchone()
    if row:
        return int(row["id"])

    # If nothing, list available subclasses for that class
    rows = conn.execute(
        "select name from subclasses where class_id=? order by name;",
        (class_id,),
    ).fetchall()
    names = [r["name"] for r in rows]
    raise SystemExit(f"Subclass not found: {subclass_name!r}. Available: {names}")

def set_character_subclass(conn: sqlite3.Connection, character_id: int, class_id: int, subclass_id: int) -> None:
    if not table_exists(conn, "character_levels"):
        raise SystemExit("Missing character_levels table.")

    cols = colset(conn, "character_levels")
    if "subclass_id" not in cols:
        raise SystemExit("character_levels has no subclass_id column.")

    # Choose the row for this class (assumes one row per class for now)
    row = conn.execute(
        "select rowid, subclass_id from character_levels where character_id=? and class_id=? limit 1;",
        (character_id, class_id),
    ).fetchone()
    if not row:
        raise SystemExit("No character_levels row found for that character/class. Seed the class level first.")

    # If already set, do nothing
    if row["subclass_id"] == subclass_id:
        return

    updates = ["subclass_id=?"]
    params: list[object] = [subclass_id]

    ts = now_iso()
    if "updated_at" in cols:
        updates.append("updated_at=?")
        params.append(ts)

    params += [character_id, class_id]
    conn.execute(
        f"update character_levels set {', '.join(updates)} where character_id=? and class_id=?;",
        params,
    )

def fetch_subclass_feature_ids(conn: sqlite3.Connection, subclass_id: int, level: int) -> list[int]:
    q = """
    select distinct f.id
    from subclass_features sf
    join features f on f.id = sf.feature_id
    where sf.subclass_id = ?
      and f.level <= ?
    order by f.level, f.name;
    """
    rows = conn.execute(q, (subclass_id, level)).fetchall()
    return [int(r["id"]) for r in rows]

def already_has_feature(conn: sqlite3.Connection, character_id: int, feature_id: int) -> bool:
    return conn.execute(
        "select 1 from character_features where character_id=? and feature_id=? limit 1;",
        (character_id, feature_id),
    ).fetchone() is not None

def insert_character_feature(conn: sqlite3.Connection, character_id: int, feature_id: int) -> None:
    cols = colset(conn, "character_features")
    insert_cols = ["character_id", "feature_id"]
    insert_vals: list[object] = [character_id, feature_id]

    ts = now_iso()
    if "created_at" in cols:
        insert_cols.append("created_at")
        insert_vals.append(ts)
    if "updated_at" in cols:
        insert_cols.append("updated_at")
        insert_vals.append(ts)

    q = f"insert into character_features ({', '.join(insert_cols)}) values ({', '.join(['?']*len(insert_cols))});"
    conn.execute(q, insert_vals)

def main() -> None:
    ap = argparse.ArgumentParser(description="Set a character's subclass and apply subclass features up to a level.")
    ap.add_argument("--character-id", type=int, required=True)
    ap.add_argument("--class", dest="class_name", required=True)
    ap.add_argument("--subclass", dest="subclass_name", required=True)
    ap.add_argument("--level", type=int, required=True)
    args = ap.parse_args()

    p = db_path()
    if not p.exists():
        raise SystemExit(f"DB not found: {p}")

    with connect(p) as conn:
        for t in ["characters", "classes", "subclasses", "subclass_features", "features", "character_levels", "character_features"]:
            if not table_exists(conn, t):
                raise SystemExit(f"Missing required table: {t}")

        if not character_exists(conn, args.character_id):
            raise SystemExit(f"Character not found: id={args.character_id}")

        class_id = get_class_id(conn, args.class_name)
        subclass_id = find_subclass_id(conn, class_id, args.subclass_name)

        # Set subclass on character_levels
        set_character_subclass(conn, args.character_id, class_id, subclass_id)

        # Apply subclass features up to level
        feature_ids = fetch_subclass_feature_ids(conn, subclass_id, args.level)
        added = 0
        skipped = 0
        for fid in feature_ids:
            if already_has_feature(conn, args.character_id, fid):
                skipped += 1
                continue
            insert_character_feature(conn, args.character_id, fid)
            added += 1

        conn.commit()

        # Report
        sc_name = conn.execute("select name from subclasses where id=?;", (subclass_id,)).fetchone()["name"]
        print(f"Subclass set/applied: {args.class_name} -> {sc_name} up to level {args.level}")
        print(f"Subclass features considered: {len(feature_ids)} | added: {added} | already present: {skipped}")

        rows = conn.execute(
            """
            select f.level, f.name
            from character_features cf
            join features f on f.id = cf.feature_id
            where cf.character_id = ?
            order by f.level, f.name
            limit 80;
            """,
            (args.character_id,),
        ).fetchall()
        print("\nCharacter features (first 80):")
        for r in rows:
            print(f" - L{r['level']}: {r['name']}")

if __name__ == "__main__":
    main()
PY

chmod +x tools/apply_subclass_features.py
echo "==> Added tools/apply_subclass_features.py"
echo "Run (example):"
echo "  python tools/apply_subclass_features.py --character-id 2 --class Wizard --subclass Evocation --level 2"
