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

DEFAULT_DB = Path(".data/sqlite/dnd_rules.db")

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
        raise SystemExit(f"DB not found: {path}")

    with connect(path) as conn:
        print(f"DB: {path}")

        # 1) SQLite internal integrity
        integrity = conn.execute("PRAGMA integrity_check;").fetchone()[0]
        print("\nPRAGMA integrity_check:")
        print(" ", integrity)

        # 2) Foreign keys configured?
        fk = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
        print("\nPRAGMA foreign_keys:")
        print(" ", "ON" if fk else "OFF")

        # 3) Foreign key violations (only meaningful if you created FK constraints)
        try:
            rows = conn.execute("PRAGMA foreign_key_check;").fetchall()
            print("\nPRAGMA foreign_key_check:")
            if not rows:
                print("  OK (no violations)")
            else:
                print(f"  Violations: {len(rows)}")
                for r in rows[:25]:
                    # (table, rowid, parent, fkid)
                    print("  ", dict(r))
                if len(rows) > 25:
                    print("  ... (truncated)")
        except sqlite3.OperationalError as e:
            print("\nPRAGMA foreign_key_check not available or errored:")
            print(" ", e)

if __name__ == "__main__":
    main()