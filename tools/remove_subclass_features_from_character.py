#!/usr/bin/env python3
from __future__ import annotations

import argparse
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

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--character-id", type=int, required=True)
    args = ap.parse_args()

    p = db_path()
    if not p.exists():
        raise SystemExit(f"DB not found: {p}")

    with connect(p) as conn:
        n = conn.execute(
            """
            delete from character_features
            where character_id = ?
              and feature_id in (
                select id from features
                where subclass_source_key is not null
                  and trim(subclass_source_key) != ''
              );
            """,
            (args.character_id,),
        ).rowcount
        conn.commit()
        print(f"Removed {n} subclass-tagged features from character_id={args.character_id}")

if __name__ == "__main__":
    main()
