#!/usr/bin/env bash
set -euo pipefail

mkdir -p tools scripts

cat > tools/apply_class_features.py <<'PY'
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
    return conn.execute(
        "select 1 from sqlite_master where type='table' and name=?;",
        (name,),
    ).fetchone() is not None

def colset(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"pragma table_info({table});").fetchall()}

def get_class_id(conn: sqlite3.Connection, class_name: str) -> int:
    row = conn.execute(
        "select id from classes where lower(name)=lower(?) limit 1;",
        (class_name,),
    ).fetchone()
    if not row:
        raise SystemExit(f"Class not found: {class_name!r}")
    return int(row["id"])

def character_exists(conn: sqlite3.Connection, character_id: int) -> bool:
    return conn.execute(
        "select 1 from characters where id=? limit 1;",
        (character_id,),
    ).fetchone() is not None

def fetch_features_for_class_up_to_level(conn: sqlite3.Connection, class_id: int, level: int) -> list[int]:
    # IMPORTANT: exclude subclass features here.
    # Subclass features should be applied via subclass pipeline, not class pipeline.
    q = """
    select distinct f.id
    from class_features cf
    join features f on f.id = cf.feature_id
    where cf.class_id = ?
      and f.level <= ?
      and (f.subclass_source_key is null or trim(f.subclass_source_key) = '')
    order by f.level, f.name;
    """
    rows = conn.execute(q, (class_id, level)).fetchall()
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
    ap = argparse.ArgumentParser(description="Apply class features (excluding subclass features) up to a level onto a character.")
    ap.add_argument("--character-id", type=int, required=True)
    ap.add_argument("--class", dest="class_name", required=True, help="Class name, e.g. Wizard")
    ap.add_argument("--level", type=int, required=True, help="Apply features with f.level <= level")
    args = ap.parse_args()

    p = db_path()
    if not p.exists():
        raise SystemExit(f"DB not found: {p}")

    with connect(p) as conn:
        for t in ["characters", "classes", "class_features", "features", "character_features"]:
            if not table_exists(conn, t):
                raise SystemExit(f"Missing required table: {t}")

        if not character_exists(conn, args.character_id):
            raise SystemExit(f"Character not found: id={args.character_id}")

        class_id = get_class_id(conn, args.class_name)
        feature_ids = fetch_features_for_class_up_to_level(conn, class_id, args.level)

        added = 0
        skipped = 0
        for fid in feature_ids:
            if already_has_feature(conn, args.character_id, fid):
                skipped += 1
                continue
            insert_character_feature(conn, args.character_id, fid)
            added += 1

        conn.commit()
        print(f"Applied class features (filtered): class={args.class_name} up to level={args.level}")
        print(f"Feature rows considered: {len(feature_ids)} | added: {added} | already present: {skipped}")

        rows = conn.execute(
            """
            select f.level, f.name
            from character_features cf
            join features f on f.id = cf.feature_id
            where cf.character_id = ?
            order by f.level, f.name
            limit 60;
            """,
            (args.character_id,),
        ).fetchall()
        print("\nCharacter features (first 60):")
        for r in rows:
            print(f" - L{r['level']}: {r['name']}")

if __name__ == "__main__":
    main()
PY

chmod +x tools/apply_class_features.py
echo "==> Overwrote tools/apply_class_features.py (syntax fixed + subclass filter added)."
