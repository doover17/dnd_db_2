from __future__ import annotations

if __name__ == "__main__":
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(ROOT / "src"))
    


import os
import sqlite3
from pathlib import Path
from typing import Iterable

DEFAULT_DB = Path(".data/sqlite/dnd_rules.db")

def db_path() -> Path:
    return Path(os.environ.get("DND_DB_PATH", str(DEFAULT_DB))).expanduser().resolve()

def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def list_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name;"
    ).fetchall()
    return [r["name"] for r in rows]

def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"pragma table_info({table});").fetchall()}

def safe_count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"select count(*) from {table};").fetchone()[0])

def pct(n: int, d: int) -> str:
    return "0%" if d == 0 else f"{(n/d)*100:.1f}%"

def main() -> None:
    path = db_path()
    if not path.exists():
        raise SystemExit(f"DB not found: {path}")

    with connect(path) as conn:
        tables = list_tables(conn)
        print(f"DB: {path}")
        print(f"Tables: {len(tables)}")

        # Primary “content” tables we care about early
        focus = [t for t in ["spells", "items", "classes", "subclasses", "features", "races", "monsters", "entities_raw"] if t in tables]

        print("\nRow counts:")
        for t in focus:
            print(f"  {t:<12} {safe_count(conn, t)}")

        # Generic “key columns should not be blank” checks
        print("\nNull/blank checks (if columns exist):")
        checks = {
            "name": "name is null or trim(name)=''",
            "slug": "slug is null or trim(slug)=''",
            "index": '"index" is null or trim("index")=\'\'',
            "source_key": "source_key is null or trim(source_key)=''",
            "entity_type": "entity_type is null or trim(entity_type)=''",
        }

        for t in focus:
            cols = columns(conn, t)
            total = safe_count(conn, t)
            if total == 0:
                continue

            any_printed = False
            for col, where in checks.items():
                if col not in cols:
                    continue
                bad = int(conn.execute(f"select count(*) from {t} where {where};").fetchone()[0])
                if bad:
                    if not any_printed:
                        print(f"\n  {t}:")
                        any_printed = True
                    print(f"    {col:<10} bad={bad} ({pct(bad,total)})")

        # Duplicate-ish checks for common unique keys
        print("\nDuplicate checks (if columns exist):")
        dup_candidates: list[tuple[str, list[str]]] = [
            ("spells", ["slug", "name", "index", "source_key"]),
            ("items", ["slug", "name", "index", "source_key"]),
            ("classes", ["slug", "name", "index", "source_key"]),
            ("features", ["slug", "name", "index", "source_key"]),
            ("entities_raw", ["source_key"]),
        ]

        for t, keys in dup_candidates:
            if t not in tables:
                continue
            cols = columns(conn, t)
            usable = [k for k in keys if k in cols]
            if not usable:
                continue

            # Try first usable key
            k = usable[0]
            q = f"""
            select {k} as k, count(*) as c
            from {t}
            where {k} is not null and trim({k}) != ''
            group by {k}
            having count(*) > 1
            order by c desc
            limit 10;
            """
            rows = conn.execute(q).fetchall()
            if rows:
                print(f"\n  {t} duplicates by {k}:")
                for r in rows:
                    print(f"    {r['k']}  x{r['c']}")

if __name__ == "__main__":
    main()