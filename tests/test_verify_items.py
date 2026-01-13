from __future__ import annotations

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from sqlmodel import Session, select

from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.db.upsert import upsert_raw_entity
from dnd_db.models.item import Item
from dnd_db.models.source import Source
from dnd_db.verify.items import verify_items


def test_verify_items_passes(tmp_path: Path) -> None:
    db_path = tmp_path / "items-verify.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        source = Source(name="5e-bits", base_url="https://example.com")
        session.add(source)
        session.commit()
        session.refresh(source)

        payload = {
            "index": "rope-hempen",
            "name": "Rope, hempen",
            "url": "/api/equipment/rope-hempen",
        }
        raw_entity, _, _ = upsert_raw_entity(
            session,
            source_id=source.id,
            entity_type="equipment",
            source_key="rope-hempen",
            payload=payload,
            name=payload.get("name"),
        )

        session.add(
            Item(
                source_id=source.id,
                raw_entity_id=raw_entity.id,
                source_key="rope-hempen",
                name="Rope, hempen",
            )
        )
        session.commit()

        report = verify_items(session)

    assert report["errors"] == []


def test_verify_items_missing_raw(tmp_path: Path) -> None:
    db_path = tmp_path / "items-verify-missing.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        source = Source(name="5e-bits", base_url="https://example.com")
        session.add(source)
        session.commit()
        session.refresh(source)

        session.add(
            Item(
                source_id=source.id,
                raw_entity_id=999,
                source_key="missing",
                name="Missing",
            )
        )
        session.commit()

        report = verify_items(session)

    assert any("Item missing raw entity" in error for error in report["errors"])


def test_verify_items_wrong_raw_type(tmp_path: Path) -> None:
    db_path = tmp_path / "items-verify-wrong.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        source = Source(name="5e-bits", base_url="https://example.com")
        session.add(source)
        session.commit()
        session.refresh(source)

        payload = {
            "index": "acid-arrow",
            "name": "Acid Arrow",
            "url": "/api/spells/acid-arrow",
        }
        raw_entity, _, _ = upsert_raw_entity(
            session,
            source_id=source.id,
            entity_type="spell",
            source_key="acid-arrow",
            payload=payload,
            name=payload.get("name"),
        )

        session.add(
            Item(
                source_id=source.id,
                raw_entity_id=raw_entity.id,
                source_key="acid-arrow",
                name="Acid Arrow",
            )
        )
        session.commit()

        report = verify_items(session)

    assert any("Item raw entity type mismatch" in error for error in report["errors"])
