#!/usr/bin/env python3
from __future__ import annotations

import sqlite3

def inventory_item_fk_column(conn: sqlite3.Connection) -> str:
    """
    Return the column in inventory_items that references items.* via FK.
    Raises if not found.
    """
    fks = conn.execute("pragma foreign_key_list(inventory_items);").fetchall()
    for fk in fks:
        if fk["table"] == "items":
            return fk["from"]
    # Fallback heuristic: pick the only non-character *_id column
    cols = [r["name"] for r in conn.execute("pragma table_info(inventory_items);").fetchall()]
    candidates = [c for c in cols if c.endswith("_id") and c not in ("character_id",)]
    if len(candidates) == 1:
        return candidates[0]
    raise RuntimeError(f"Could not detect inventory_items -> items FK column. Columns={cols}, fks={[dict(x) for x in fks]}")
