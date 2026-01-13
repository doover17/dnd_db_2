#!/usr/bin/env bash
set -euo pipefail

python - <<'PY'
from pathlib import Path
import re

p = Path("tools/apply_class_features.py")
txt = p.read_text(encoding="utf-8")

# Patch the query in fetch_features_for_class_up_to_level to exclude subclass features
pattern = re.compile(r"""
def\ fetch_features_for_class_up_to_level\(.*?\)\ ->\ list\[int\]:\s*
\s*q\s*=\s*"""\n(.*?)\n\s*"""\s*
""", re.DOTALL | re.VERBOSE)

m = pattern.search(txt)
if not m:
    raise SystemExit("Could not find fetch_features_for_class_up_to_level() query block to patch.")

q_body = m.group(1)

# Only patch if not already present
if "subclass_source_key is null" not in q_body.lower():
    q_body_new = q_body.replace(
        "and f.level <= ?",
        "and f.level <= ?\n      and (f.subclass_source_key is null or f.subclass_source_key = '')"
    )
    txt = txt[:m.start(1)] + q_body_new + txt[m.end(1):]
    p.write_text(txt, encoding="utf-8")
    print("Patched tools/apply_class_features.py to exclude subclass features (subclass_source_key IS NULL).")
else:
    print("apply_class_features.py already excludes subclass features.")
PY

echo "==> Done."
echo "Next: create a fresh demo character and apply class+subclass to see the intended behavior."
