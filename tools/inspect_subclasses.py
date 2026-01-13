#!/usr/bin/env python3
from __future__ import annotations

import os, sqlite3
from pathlib import Path

DEFAULT_DB = Path("./data/sqlite/dnd_rules.db")

def db_path() -> Path:
    return Path(os.environ.get("DND_DB_PATH", str(DEFAULT_DB))).expanduser().resolve()

def connect(p: Path) -> sqlite3.Connection:
    c = sqlite3.connect(str(p))
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON;")
    return c

def main() -> None:
    p = db_path()
    if not p.exists():
        raise SystemExit(f"DB not found: {p}")

    with connect(p) as conn:
        cols = conn.execute("pragma table_info(subclasses);").fetchall()
        print("subclasses columns:")
        for c in cols:
            print(f" - {c['name']:<22} {c['type'] or ''}{' (PK)' if c['pk'] else ''}")

        rows = conn.execute("select * from subclasses order by id limit 12;").fetchall()
        print(f"\nsubclasses sample rows ({len(rows)}):")
        for r in rows:
            # Print only a few common fields if present
            keys = r.keys()
            parts = []
            for k in ["id", "name", "source_key", "api_url", "class_source_key", "class_name", "parent_class", "created_at"]:
                if k in keys and r[k] is not None:
                    s = str(r[k])
                    if k in ("api_url",) and len(s) > 50:
                        s = s[:50] + "..."
                    parts.append(f"{k}={s}")
            if not parts:
                parts = [f"id={r['id']}", f"name={r['name']}" ] if "id" in keys and "name" in keys else [str(dict(r))]
            print(" - " + " | ".join(parts))

if __name__ == "__main__":
    main()
