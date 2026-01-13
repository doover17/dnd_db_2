from __future__ import annotations

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from sqlmodel import Session

from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.db.upsert import upsert_raw_entity
from dnd_db.models.source import Source
from dnd_db.snapshots import create_snapshot, diff_snapshots


def test_snapshots_diff_detects_changes(tmp_path: Path) -> None:
    db_path = tmp_path / "snapshots.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        source = Source(name="5e-bits", base_url="https://example.com")
        session.add(source)
        session.commit()
        session.refresh(source)

        payload = {"index": "acid-arrow", "name": "Acid Arrow", "level": 2}
        upsert_raw_entity(
            session,
            source_id=source.id,
            entity_type="spell",
            source_key="acid-arrow",
            payload=payload,
            name=payload.get("name"),
        )

        snapshot_one = create_snapshot(session, source.id)

        updated_payload = {"index": "acid-arrow", "name": "Acid Arrow", "level": 3}
        upsert_raw_entity(
            session,
            source_id=source.id,
            entity_type="spell",
            source_key="acid-arrow",
            payload=updated_payload,
            name=updated_payload.get("name"),
        )

        snapshot_two = create_snapshot(session, source.id)
        report = diff_snapshots(snapshot_one, snapshot_two)

    assert any("Hash raw_entities_spell changed" in entry for entry in report["changes"])
