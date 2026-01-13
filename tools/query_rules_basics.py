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

def class_features_by_level(conn: sqlite3.Connection, class_name: str, level: int) -> None:
    q = """
    select f.level, f.name, f.desc
    from classes c
    join class_features cf on cf.class_id = c.id
    join features f on f.id = cf.feature_id
    where lower(c.name) = lower(?)
      and f.level = ?
    order by f.name;
    """
    rows = conn.execute(q, (class_name, level)).fetchall()
    print(f"\n{class_name} features at level {level}: {len(rows)}")
    for r in rows[:30]:
        print(f" - {r['name']}")
    if len(rows) > 30:
        print(" ... (truncated)")

def spells_for_class(conn: sqlite3.Connection, class_name: str) -> None:
    q = """
    select s.level, s.name
    from classes c
    join spell_classes sc on sc.class_id = c.id
    join spells s on s.id = sc.spell_id
    where lower(c.name) = lower(?)
    order by s.level, s.name
    limit 80;
    """
    rows = conn.execute(q, (class_name,)).fetchall()
    print(f"\nSpells for {class_name} (first {len(rows)}):")
    for r in rows:
        print(f" - L{r['level']}: {r['name']}")

def main() -> None:
    p = db_path()
    if not p.exists():
        raise SystemExit(f"DB not found: {p}")

    with connect(p) as conn:
        # Two quick “character sheet-ish” checks
        class_features_by_level(conn, "Wizard", 2)
        spells_for_class(conn, "Wizard")

if __name__ == "__main__":
    main()
