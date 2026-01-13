from __future__ import annotations

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from sqlmodel import Session

from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.db.upsert import upsert_raw_entity
from dnd_db.models.monster import Monster
from dnd_db.models.source import Source
from dnd_db.verify.monsters import verify_monsters


def test_verify_monsters_passes(tmp_path: Path) -> None:
    db_path = tmp_path / "monsters-verify.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        source = Source(name="5e-bits", base_url="https://example.com")
        session.add(source)
        session.commit()
        session.refresh(source)

        payload = {
            "index": "guard",
            "name": "Guard",
            "url": "/api/monsters/guard",
        }
        raw_entity, _, _ = upsert_raw_entity(
            session,
            source_id=source.id,
            entity_type="monster",
            source_key="guard",
            payload=payload,
            name=payload.get("name"),
        )

        session.add(
            Monster(
                source_id=source.id,
                raw_entity_id=raw_entity.id,
                source_key="guard",
                name="Guard",
            )
        )
        session.commit()

        report = verify_monsters(session)

    assert report["errors"] == []


def test_verify_monsters_missing_raw(tmp_path: Path) -> None:
    db_path = tmp_path / "monsters-verify-missing.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        source = Source(name="5e-bits", base_url="https://example.com")
        session.add(source)
        session.commit()
        session.refresh(source)

        session.add(
            Monster(
                source_id=source.id,
                raw_entity_id=999,
                source_key="missing",
                name="Missing",
            )
        )
        session.commit()

        report = verify_monsters(session)

    assert any("Monster missing raw entity" in error for error in report["errors"])


def test_verify_monsters_wrong_raw_type(tmp_path: Path) -> None:
    db_path = tmp_path / "monsters-verify-wrong.db"
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
            Monster(
                source_id=source.id,
                raw_entity_id=raw_entity.id,
                source_key="acid-arrow",
                name="Acid Arrow",
            )
        )
        session.commit()

        report = verify_monsters(session)

    assert any(
        "Monster raw entity type mismatch" in error for error in report["errors"]
    )
