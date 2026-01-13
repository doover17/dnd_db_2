from __future__ import annotations

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from sqlmodel import Session

from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.db.upsert import upsert_raw_entity
from dnd_db.models.condition import Condition
from dnd_db.models.source import Source
from dnd_db.verify.conditions import verify_conditions


def test_verify_conditions_passes(tmp_path: Path) -> None:
    db_path = tmp_path / "conditions-verify.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        source = Source(name="5e-bits", base_url="https://example.com")
        session.add(source)
        session.commit()
        session.refresh(source)

        payload = {
            "index": "blinded",
            "name": "Blinded",
            "url": "/api/conditions/blinded",
        }
        raw_entity, _, _ = upsert_raw_entity(
            session,
            source_id=source.id,
            entity_type="condition",
            source_key="blinded",
            payload=payload,
            name=payload.get("name"),
        )

        session.add(
            Condition(
                source_id=source.id,
                raw_entity_id=raw_entity.id,
                source_key="blinded",
                name="Blinded",
            )
        )
        session.commit()

        report = verify_conditions(session)

    assert report["errors"] == []


def test_verify_conditions_missing_raw(tmp_path: Path) -> None:
    db_path = tmp_path / "conditions-verify-missing.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        source = Source(name="5e-bits", base_url="https://example.com")
        session.add(source)
        session.commit()
        session.refresh(source)

        session.add(
            Condition(
                source_id=source.id,
                raw_entity_id=999,
                source_key="missing",
                name="Missing",
            )
        )
        session.commit()

        report = verify_conditions(session)

    assert any("Condition missing raw entity" in error for error in report["errors"])


def test_verify_conditions_wrong_raw_type(tmp_path: Path) -> None:
    db_path = tmp_path / "conditions-verify-wrong.db"
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
            Condition(
                source_id=source.id,
                raw_entity_id=raw_entity.id,
                source_key="acid-arrow",
                name="Acid Arrow",
            )
        )
        session.commit()

        report = verify_conditions(session)

    assert any(
        "Condition raw entity type mismatch" in error for error in report["errors"]
    )
