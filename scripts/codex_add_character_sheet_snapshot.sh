#!/usr/bin/env bash
set -euo pipefail

mkdir -p tools scripts

cat > tools/character_sheet_snapshot.py <<'PY'
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path
from collections import defaultdict

DEFAULT_DB = Path("./data/sqlite/dnd_rules.db")

def db_path() -> Path:
    return Path(os.environ.get("DND_DB_PATH", str(DEFAULT_DB))).expanduser().resolve()

def connect(p: Path) -> sqlite3.Connection:
    c = sqlite3.connect(str(p))
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON;")
    return c

def main() -> None:
    ap = argparse.ArgumentParser(description="Print a compact character sheet snapshot (levels, subclass, features, spells).")
    ap.add_argument("--character-id", type=int, required=True)
    ap.add_argument("--max", type=int, default=200, help="Max items to display per section")
    args = ap.parse_args()

    p = db_path()
    if not p.exists():
        raise SystemExit(f"DB not found: {p}")

    with connect(p) as conn:
        ch = conn.execute("select * from characters where id=?;", (args.character_id,)).fetchone()
        if not ch:
            raise SystemExit(f"Character not found: id={args.character_id}")

        name = ch["name"] if "name" in ch.keys() else f"Character {args.character_id}"
        print(f"== {name} (id={args.character_id}) ==")

        # Levels + subclass
        lvl_rows = conn.execute(
            """
            select cl.class_id, c.name as class_name, cl.level, cl.subclass_id, sc.name as subclass_name
            from character_levels cl
            join classes c on c.id = cl.class_id
            left join subclasses sc on sc.id = cl.subclass_id
            where cl.character_id=?
            order by c.name;
            """,
            (args.character_id,),
        ).fetchall()

        if lvl_rows:
            print("\nLevels:")
            for r in lvl_rows:
                line = f" - {r['class_name']} {r['level']}"
                if r["subclass_name"]:
                    line += f" ({r['subclass_name']})"
                print(line)
        else:
            print("\nLevels: (none)")

        # Features grouped by level
        feat_rows = conn.execute(
            """
            select f.level, f.name
            from character_features cf
            join features f on f.id = cf.feature_id
            where cf.character_id=?
            order by f.level, f.name;
            """,
            (args.character_id,),
        ).fetchall()

        feats_by_level: dict[int, list[str]] = defaultdict(list)
        for r in feat_rows[: args.max]:
            feats_by_level[int(r["level"])].append(r["name"])

        print("\nFeatures:")
        if not feat_rows:
            print(" (none)")
        else:
            for lvl in sorted(feats_by_level.keys()):
                print(f" L{lvl}:")
                for n in feats_by_level[lvl]:
                    print(f"  - {n}")

        # Known spells grouped by spell level
        def spell_section(title: str, table: str) -> None:
            rows = conn.execute(
                f"""
                select s.level, s.name, s.school
                from {table} cs
                join spells s on s.id = cs.spell_id
                where cs.character_id=?
                order by s.level, s.name;
                """,
                (args.character_id,),
            ).fetchall()

            print(f"\n{title}:")
            if not rows:
                print(" (none)")
                return

            by_lvl: dict[int, list[str]] = defaultdict(list)
            for r in rows[: args.max]:
                lvl = int(r["level"])
                by_lvl[lvl].append(f"{r['name']} ({r['school']})")

            for lvl in sorted(by_lvl.keys()):
                hdr = "Cantrips" if lvl == 0 else f"Level {lvl}"
                print(f" {hdr}:")
                for s in by_lvl[lvl]:
                    print(f"  - {s}")

        spell_section("Known spells", "character_known_spells")
        spell_section("Prepared spells", "character_prepared_spells")

        # Inventory (counts only for now)
        inv = conn.execute(
            "select count(*) as n from inventory_items where character_id=?;",
            (args.character_id,),
        ).fetchone()
        print(f"\nInventory items: {int(inv['n']) if inv else 0}")

if __name__ == "__main__":
    main()
PY

chmod +x tools/character_sheet_snapshot.py
echo "==> Added tools/character_sheet_snapshot.py"
echo "Run:"
echo "  python tools/character_sheet_snapshot.py --character-id 2"
