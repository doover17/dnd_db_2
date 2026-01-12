from __future__ import annotations

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from sqlmodel import Session, select

from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.db.upsert import upsert_raw_entity
from dnd_db.models.raw_entity import RawEntity
from dnd_db.models.source import Source


def test_upsert_raw_entity_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "raw_entities.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    payload = {
        "index": "acid-arrow",
        "name": "Acid Arrow",
        "level": 2,
        "school": {"index": "evocation", "name": "Evocation"},
        "srd": True,
        "url": "/api/spells/acid-arrow",
    }

    with Session(engine) as session:
        source = Source(name="5e-bits")
        session.add(source)
        session.commit()
        session.refresh(source)

        entity, created, updated = upsert_raw_entity(
            session,
            source_id=source.id,
            entity_type="spell",
            source_key=payload["index"],
            payload=payload,
            name=payload["name"],
            srd=payload.get("srd"),
            url=payload.get("url"),
        )
        assert created is True
        assert updated is False
        first_hash = entity.raw_hash

        entity, created, updated = upsert_raw_entity(
            session,
            source_id=source.id,
            entity_type="spell",
            source_key=payload["index"],
            payload=payload,
            name=payload["name"],
            srd=payload.get("srd"),
            url=payload.get("url"),
        )
        assert created is False
        assert updated is False
        assert entity.raw_hash == first_hash

        payload_changed = {**payload, "level": 3}
        entity, created, updated = upsert_raw_entity(
            session,
            source_id=source.id,
            entity_type="spell",
            source_key=payload["index"],
            payload=payload_changed,
            name=payload_changed["name"],
            srd=payload_changed.get("srd"),
            url=payload_changed.get("url"),
        )
        assert created is False
        assert updated is True
        assert entity.raw_hash != first_hash

        raw_entities = session.exec(select(RawEntity)).all()
        assert len(raw_entities) == 1
