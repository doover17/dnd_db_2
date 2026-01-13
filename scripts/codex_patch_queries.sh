#!/usr/bin/env bash
set -euo pipefail

echo "==> Repo root: $(pwd)"

# 0) Safety checks
test -f tools/query_playground.py || { echo "Missing tools/query_playground.py"; exit 1; }
mkdir -p tools scripts

# 1) Patch query_playground.py to prefer spell_desc/higher_level
python - <<'PY'
from __future__ import annotations
from pathlib import Path
import re

path = Path("tools/query_playground.py")
txt = path.read_text(encoding="utf-8")

# Find the "description-ish" loop and replace it.
# We look for the exact block:
#   for k in ["desc", "description", "text"]:
#       ...
pattern = re.compile(
    r"""
    for\ k\ in\ \[\s*"desc"\s*,\s*"description"\s*,\s*"text"\s*\]\s*:\s*
    \n\s*if\ k\ in\ r\.keys\(\)\s*and\ r\[k\]\s*:\s*
    \n\s*s\s*=\s*str\(r\[k\]\)\s*
    \n\s*s\s*=\s*s\[:400\]\s*\+\s*\(""\.\.\."\s*if\ len\(s\)\s*>\s*400\ else\ ""\)\s*
    \n\s*print\(f"\\s*\{k\}:\ \{s\}"\)\s*
    \n\s*break
    """,
    re.VERBOSE,
)

replacement = """for k in ["spell_desc", "higher_level", "desc", "description", "text"]:
            if k in r.keys() and r[k]:
                s = str(r[k])
                s = s[:600] + ("..." if len(s) > 600 else "")
                print(f"  {k}: {s}")
                break"""

new_txt, n = pattern.subn(replacement, txt, count=1)

if n == 0:
    # Fallback: insert a new block if the old one isn't found (schema drift).
    # We’ll try to insert right after the "Common descriptive columns" section.
    anchor = '        # Try to show description-ish content\n'
    if anchor in txt:
        parts = txt.split(anchor, 1)
        new_block = anchor + "        " + replacement + "\n\n"
        new_txt = parts[0] + new_block + parts[1]
        n = 1

if n == 0:
    raise SystemExit("Could not find a patch location in tools/query_playground.py (file differs from expected).")

path.write_text(new_txt, encoding="utf-8")
print("Patched tools/query_playground.py (spell_desc/higher_level display).")
PY

# 2) Add tools/query_rules_basics.py (class->features by level, class->spells)
cat > tools/query_rules_basics.py <<'PY'
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
PY

chmod +x tools/query_rules_basics.py
chmod +x scripts/codex_patch_queries.sh

echo "==> Done."
echo "Next commands:"
echo "  python tools/query_playground.py --spell \"magic missile\""
echo "  python tools/query_rules_basics.py"
