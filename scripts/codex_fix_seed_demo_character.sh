#!/usr/bin/env bash
set -euo pipefail

python - <<'PY'
from __future__ import annotations
from pathlib import Path
import re

p = Path("tools/seed_demo_character.py")
txt = p.read_text(encoding="utf-8")

# Patch: when created_at/updated_at exist, insert datetime('now') instead of NULL.
# We'll replace the block where it appends created_at/updated_at.
pattern = re.compile(r"""
\s*#\s*set\s*created_at/updated_at\s*if\s*present\s*\(optional\)\s*
\s*for\s+ts\s+in\s+\["created_at",\s*"updated_at"\]\s*:\s*
\s*if\s+ts\s+in\s+ccols\s*:\s*
\s*fields\.append\(ts\)\s*
\s*vals\.append\(None\)\s*#\s*let\s*DB\s*default.*?\n
""", re.VERBOSE | re.DOTALL)

replacement = """
        # set created_at/updated_at if present (NOT NULL safe)
        # Use SQLite's datetime('now') so inserts always satisfy NOT NULL constraints.
        # We'll inject these as SQL expressions by tracking them separately.
        sql_expr_fields = []
        for ts in ["created_at", "updated_at"]:
            if ts in ccols:
                sql_expr_fields.append(ts)
"""

# If our older block isn't present, do a simpler targeted replace of "vals.append(None)" lines.
if pattern.search(txt):
    txt = pattern.sub(replacement, txt, count=1)
else:
    # Add sql_expr_fields list near fields/vals init if missing
    if "sql_expr_fields" not in txt:
        txt = txt.replace("        fields = []\n        vals = []\n",
                          "        fields = []\n        vals = []\n        sql_expr_fields = []\n")

    txt = txt.replace(
        "                fields.append(ts)\n                vals.append(None)  # let DB default if any; otherwise NULL is fine for a demo\n",
        "                sql_expr_fields.append(ts)\n"
    )

# Now patch the insert statement builder to include datetime('now') for those sql_expr_fields.
# Find the insert q assignment and modify.
# Original:
# q = f"insert into characters ({', '.join(fields)}) values ({', '.join(['?']*len(fields))});"
# We'll build merged lists.
if "insert into characters" in txt and "sql_expr_fields" in txt and "datetime('now')" not in txt:
    txt = txt.replace(
        "                q = f\"insert into characters ({', '.join(fields)}) values ({', '.join(['?']*len(fields))});\"",
        """                all_fields = fields + sql_expr_fields
                placeholders = (['?'] * len(fields)) + ["datetime('now')" for _ in sql_expr_fields]
                q = f"insert into characters ({', '.join(all_fields)}) values ({', '.join(placeholders)});" """
    )

p.write_text(txt, encoding="utf-8")
print("Patched tools/seed_demo_character.py to satisfy NOT NULL created_at/updated_at.")
PY

echo "==> Patch applied."
echo "Run:"
echo "  python tools/seed_demo_character.py"
