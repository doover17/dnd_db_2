from __future__ import annotations

if __name__ == "__main__":
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(ROOT / "src"))


import argparse
import os
import sqlite3
from pathlib import Path

DEFAULT_DB = Path("./data/dnd_rules.db")


def db_path() -> Path:
    return Path(os.environ.get("DND_DB_PATH", str(DEFAULT_DB))).expanduser().resolve()


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return (
        conn.execute(
            "select 1 from sqlite_master where type='table' and name=?;", (name,)
        ).fetchone()
        is not None
    )


def cols(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"pragma table_info({table});").fetchall()}


def find_spell(conn: sqlite3.Connection, needle: str) -> None:
    if not table_exists(conn, "spells"):
        print("No table: spells")
        return

    c = cols(conn, "spells")
    where_parts = []
    params = {}

    if "name" in c:
        where_parts.append("lower(name) = lower(:n)")
        params["n"] = needle
        where_parts.append("lower(name) like lower(:like)")
        params["like"] = f"%{needle}%"

    if "slug" in c:
        where_parts.append("lower(slug) = lower(:n)")
    if '"index"' in c or "index" in c:
        where_parts.append('lower("index") = lower(:n)')

    if not where_parts:
        print(
            "spells table exists, but no recognizable search columns (name/slug/index)."
        )
        return

    q = f"""
    select *
    from spells
    where {" or ".join(where_parts)}
    limit 10;
    """
    rows = conn.execute(q, params).fetchall()
    if not rows:
        print(f"No spells matched: {needle!r}")
        return

    print(f"Matches ({len(rows)}):")
    for r in rows:
        # Print a compact “card”
        name = r["name"] if "name" in r.keys() else "<no name col>"
        lvl = r["level"] if "level" in r.keys() else "?"
        school = r["school"] if "school" in r.keys() else "?"
        print(f"\n- {name} (level {lvl}, {school})")

        # Common descriptive columns
        for k in ["casting_time", "range", "duration", "concentration", "ritual"]:
            if k in r.keys():
                print(f"  {k.replace('_',' ')}: {r[k]}")

        # Try to show description-ish content
        for k in ["spell_desc", "higher_level", "desc", "description", "text"]:
            if k in r.keys() and r[k]:
                s = str(r[k])
                s = s[:600] + ("..." if len(s) > 600 else "")
                print(f"  {k}: {s}")
                break

        for k in ["desc", "description", "text"]:
            if k in r.keys() and r[k]:
                s = str(r[k])
                s = s[:400] + ("..." if len(s) > 400 else "")
                print(f"  {k}: {s}")
                break


def list_top_tables(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        select name
        from sqlite_master
        where type='table' and name not like 'sqlite_%'
        order by name;
        """
    ).fetchall()
    print("Tables:")
    for r in rows:
        print(" -", r["name"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spell", help="Find spell by name/slug (exact or contains)")
    ap.add_argument("--list-tables", action="store_true", help="List tables")
    args = ap.parse_args()

    path = db_path()
    if not path.exists():
        raise SystemExit(f"DB not found: {path}")

    with connect(path) as conn:
        if args.list_tables:
            list_top_tables(conn)
        if args.spell:
            find_spell(conn, args.spell)
        if not (args.list_tables or args.spell):
            ap.print_help()


if __name__ == "__main__":
    main()
