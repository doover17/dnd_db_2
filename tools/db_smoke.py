from __future__ import annotations

if __name__ == "__main__":
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(ROOT / "src"))
    
    #!/usr/bin/env python3


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

def main() -> None:
    path = db_path()
    if not path.exists():
        raise SystemExit(f"DB not found: {path}\nSet DND_DB_PATH or create ./data/dnd_rules.db")

    with connect(path) as conn:
        ver = conn.execute("select sqlite_version() as v;").fetchone()["v"]
        print(f"DB: {path}")
        print(f"SQLite: {ver}")

        tables = conn.execute(
            "select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name;"
        ).fetchall()
        print(f"\nTables ({len(tables)}):")
        for r in tables:
            print(" -", r["name"])

        # Show columns for a few common table names if they exist
        candidates = ["spells", "items", "classes", "features", "entities_raw", "import_runs"]
        for t in candidates:
            exists = conn.execute(
                "select 1 from sqlite_master where type='table' and name=?;", (t,)
            ).fetchone()
            if not exists:
                continue

            cols = conn.execute(f"pragma table_info({t});").fetchall()
            print(f"\nColumns: {t}")
            for c in cols:
                # pragma table_info: cid, name, type, notnull, dflt_value, pk
                print(f"  - {c['name']:<24} {c['type'] or ''}{' (PK)' if c['pk'] else ''}")

        # Quick row counts for top-level tables
        print("\nQuick counts:")
        for t in ["spells", "items", "classes", "features", "entities_raw"]:
            exists = conn.execute(
                "select 1 from sqlite_master where type='table' and name=?;", (t,)
            ).fetchone()
            if not exists:
                continue
            n = conn.execute(f"select count(*) as n from {t};").fetchone()["n"]
            print(f"  {t:<12} {n}")

if __name__ == "__main__":
    main()