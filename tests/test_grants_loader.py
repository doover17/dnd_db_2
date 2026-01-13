from __future__ import annotations

from pathlib import Path
import sys

from sqlalchemy import func
from sqlmodel import Session, select

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.db.upsert import upsert_raw_entity
from dnd_db.ingest.load_grants import load_grants
from dnd_db.models.dnd_class import DndClass
from dnd_db.models.feature import Feature
from dnd_db.models.grants import GrantFeature, GrantProficiency, GrantSpell
from dnd_db.models.source import Source
from dnd_db.models.spell import Spell


def test_load_grants_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "grants.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        source = Source(name="5e-bits", base_url="https://example.com")
        session.add(source)
        session.commit()
        session.refresh(source)
        source_id = source.id

        class_payload = {
            "index": "fighter",
            "name": "Fighter",
            "starting_proficiencies": [
                {"index": "armor-light", "name": "Light Armor"}
            ],
            "spellcasting": {
                "spells": [
                    {"index": "magic-missile", "name": "Magic Missile"}
                ]
            },
            "features": [{"index": "second-wind", "name": "Second Wind"}],
        }

        raw_class, _, _ = upsert_raw_entity(
            session,
            source_id=source_id,
            entity_type="class",
            source_key="fighter",
            payload=class_payload,
            name=class_payload.get("name"),
        )

        session.add(
            DndClass(
                source_id=source_id,
                raw_entity_id=raw_class.id,
                source_key="fighter",
                name="Fighter",
            )
        )

        session.add(
            Feature(
                source_id=source_id,
                raw_entity_id=None,
                source_key="second-wind",
                name="Second Wind",
                level=1,
                class_source_key="fighter",
            )
        )

        session.add(
            Spell(
                source_id=source_id,
                raw_entity_id=None,
                source_key="magic-missile",
                name="Magic Missile",
                level=1,
            )
        )
        session.commit()

    summary = load_grants(engine=engine, source_name="5e-bits")
    assert summary["grant_proficiencies_created"] == 1
    assert summary["grant_spells_created"] == 1
    assert summary["grant_features_created"] == 1
    assert summary["missing_refs"] == 0

    summary_again = load_grants(engine=engine, source_name="5e-bits")
    assert summary_again["grant_proficiencies_created"] == 0
    assert summary_again["grant_spells_created"] == 0
    assert summary_again["grant_features_created"] == 0

    with Session(engine) as session:
        prof_count = session.exec(
            select(func.count()).select_from(GrantProficiency)
        ).one()
        spell_count = session.exec(
            select(func.count()).select_from(GrantSpell)
        ).one()
        feature_count = session.exec(
            select(func.count()).select_from(GrantFeature)
        ).one()
    assert prof_count == 1
    assert spell_count == 1
    assert feature_count == 1

    updated_payload = {
        **class_payload,
        "starting_proficiencies": [
            *class_payload["starting_proficiencies"],
            {"index": "armor-medium", "name": "Medium Armor"},
        ],
    }

    with Session(engine) as session:
        upsert_raw_entity(
            session,
            source_id=source_id,
            entity_type="class",
            source_key="fighter",
            payload=updated_payload,
            name=updated_payload.get("name"),
        )

    summary_third = load_grants(engine=engine, source_name="5e-bits")
    assert summary_third["grant_proficiencies_created"] == 1
