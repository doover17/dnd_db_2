#!/usr/bin/env bash
set -euo pipefail

mkdir -p tools scripts

# 1) Add remove_subclass_features tool (you tried to run it but it didn't exist yet)
cat > tools/remove_subclass_features_from_character.py <<'PY'
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
PY
chmod +x tools/remove_subclass_features_from_character.py

# 2) Patch apply_class_features.py by editing JUST the SQL in-place (no regex gymnastics)
python - <<'PY'
from __future__ import annotations
from pathlib import Path

p = Path("tools/apply_class_features.py")
txt = p.read_text(encoding="utf-8")

needle = """    q = """
if "def fetch_features_for_class_up_to_level" not in txt:
    raise SystemExit("apply_class_features.py doesn't look like expected (missing function).")

# Replace the whole query string block inside fetch_features_for_class_up_to_level
# with a version that excludes subclass features.
start = txt.find("def fetch_features_for_class_up_to_level")
if start == -1:
    raise SystemExit("Couldn't find fetch_features_for_class_up_to_level")

# Find the q = """ ... """ inside that function
q_start = txt.find('q = """', start)
q_end = txt.find('"""', q_start + len('q = """'))
q_end = txt.find('"""', q_end + 3)  # end of triple-quoted SQL

if q_start == -1 or q_end == -1:
    raise SystemExit("Couldn't locate triple-quoted SQL string to patch")

new_sql = """q = """
new_sql += '''
    select distinct f.id
    from class_features cf
    join features f on f.id = cf.feature_id
    where cf.class_id = ?
      and f.level <= ?
      and (f.subclass_source_key is null or trim(f.subclass_source_key) = '')
    order by f.level, f.name;
'''
new_sql += '"""'

# Build replacement: keep indentation same as original (4 spaces)
indent = "    "
replacement = indent + new_sql.replace("\n", "\n" + indent)

txt2 = txt[:q_start] + replacement + txt[q_end+3:]
p.write_text(txt2, encoding="utf-8")
print("Patched tools/apply_class_features.py: now excludes subclass_source_key features.")
PY

echo "==> Done."
echo "Next run:"
echo "  python tools/remove_subclass_features_from_character.py --character-id 2"
echo "  python tools/apply_class_features.py --character-id 2 --class Wizard --level 2"
echo "  python tools/apply_subclass_features.py --character-id 2 --class Wizard --subclass Evocation --level 2"
echo "  python tools/character_sheet_preview.py"
