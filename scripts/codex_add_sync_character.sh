#!/usr/bin/env bash
set -euo pipefail

mkdir -p tools scripts

cat > tools/sync_character_from_levels.py <<'PY'
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

def class_name(conn: sqlite3.Connection, class_id: int) -> str:
    r = conn.execute("select name from classes where id=?;", (class_id,)).fetchone()
    return r["name"] if r else f"class_id={class_id}"

def subclass_name(conn: sqlite3.Connection, subclass_id: int) -> str:
    r = conn.execute("select name from subclasses where id=?;", (subclass_id,)).fetchone()
    return r["name"] if r else f"subclass_id={subclass_id}"

def fetch_class_feature_ids(conn: sqlite3.Connection, class_id: int, level: int) -> list[int]:
    # Exclude subclass-tagged features here.
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
    ap = argparse.ArgumentParser(description="Sync character_features from character_levels (class + subclass).")
    ap.add_argument("--character-id", type=int, required=True)
    ap.add_argument("--dry-run", action="store_true", help="Compute changes but do not write")
    args = ap.parse_args()

    p = db_path()
    if not p.exists():
        raise SystemExit(f"DB not found: {p}")

    with connect(p) as conn:
        required = ["characters", "character_levels", "classes", "features", "class_features", "character_features", "subclasses", "subclass_features"]
        for t in required:
            if not table_exists(conn, t):
                raise SystemExit(f"Missing required table: {t}")

        if not character_exists(conn, args.character_id):
            raise SystemExit(f"Character not found: id={args.character_id}")

        lvl_rows = conn.execute(
            """
            select class_id, subclass_id, level
            from character_levels
            where character_id=?
            order by class_id;
            """,
            (args.character_id,),
        ).fetchall()

        if not lvl_rows:
            print("No character_levels rows found. Nothing to sync.")
            return

        total_added = 0
        total_skipped = 0

        for lr in lvl_rows:
            cid = int(lr["class_id"])
            lvl = int(lr["level"])
            scid = lr["subclass_id"]
            cname = class_name(conn, cid)

            class_feats = fetch_class_feature_ids(conn, cid, lvl)
            added = 0
            skipped = 0
            for fid in class_feats:
                if already_has_feature(conn, args.character_id, fid):
                    skipped += 1
                    continue
                if not args.dry_run:
                    insert_character_feature(conn, args.character_id, fid)
                added += 1

            print(f"\n[{cname}] level {lvl}: class features considered={len(class_feats)} added={added} skipped={skipped}")
            total_added += added
            total_skipped += skipped

            if scid is not None:
                scid_int = int(scid)
                sname = subclass_name(conn, scid_int)
                sub_feats = fetch_subclass_feature_ids(conn, scid_int, lvl)
                added2 = 0
                skipped2 = 0
                for fid in sub_feats:
                    if already_has_feature(conn, args.character_id, fid):
                        skipped2 += 1
                        continue
                    if not args.dry_run:
                        insert_character_feature(conn, args.character_id, fid)
                    added2 += 1

                print(f"[{cname} -> {sname}] up to level {lvl}: subclass features considered={len(sub_feats)} added={added2} skipped={skipped2}")
                total_added += added2
                total_skipped += skipped2

        if args.dry_run:
            print(f"\nDRY RUN: would add {total_added} feature rows (skipped existing {total_skipped}).")
            return

        conn.commit()
        print(f"\nSYNC DONE: added {total_added} feature rows (skipped existing {total_skipped}).")

        # Show a compact feature list (top 80)
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

chmod +x tools/sync_character_from_levels.py
echo "==> Added tools/sync_character_from_levels.py"
echo "Run:"
echo "  python tools/sync_character_from_levels.py --character-id 2 --dry-run"
echo "  python tools/sync_character_from_levels.py --character-id 2"
