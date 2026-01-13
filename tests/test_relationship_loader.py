from __future__ import annotations

from pathlib import Path
import sys

from sqlalchemy import func
from sqlmodel import Session, select

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.db.upsert import upsert_raw_entity
from dnd_db.ingest.load_relationships import load_relationships
from dnd_db.models.dnd_class import DndClass
from dnd_db.models.feature import Feature
from dnd_db.models.relationships import (
    ClassFeatureLink,
    SpellClassLink,
    SubclassFeatureLink,
)
from dnd_db.models.source import Source
from dnd_db.models.spell import Spell
from dnd_db.models.subclass import Subclass


def _seed_relationship_data(session: Session) -> None:
    source = Source(name="5e-bits", base_url="https://example.com")
    session.add(source)
    session.commit()
    session.refresh(source)

    class_payloads = {
        "fighter": {"index": "fighter", "name": "Fighter", "hit_die": 10},
        "wizard": {"index": "wizard", "name": "Wizard", "hit_die": 6},
    }
    subclass_payload = {"index": "evocation", "name": "Evocation"}
    spell_payloads = {
        "magic-missile": {
            "index": "magic-missile",
            "name": "Magic Missile",
            "level": 1,
            "classes": [{"index": "wizard"}, {"index": "fighter"}],
        },
        "cure-wounds": {
            "index": "cure-wounds",
            "name": "Cure Wounds",
            "level": 1,
            "classes": [{"index": "wizard"}],
        },
    }
    feature_payloads = {
        "fighting-style": {
            "index": "fighting-style",
            "name": "Fighting Style",
            "level": 1,
            "class": {"index": "fighter"},
        },
        "sculpt-spells": {
            "index": "sculpt-spells",
            "name": "Sculpt Spells",
            "level": 2,
            "subclass": {"index": "evocation"},
        },
    }

    raw_class_entities = {}
    for key, payload in class_payloads.items():
        raw_entity, _, _ = upsert_raw_entity(
            session,
            source_id=source.id,
            entity_type="class",
            source_key=key,
            payload=payload,
            name=payload.get("name"),
        )
        raw_class_entities[key] = raw_entity

    raw_subclass, _, _ = upsert_raw_entity(
        session,
        source_id=source.id,
        entity_type="subclass",
        source_key=subclass_payload["index"],
        payload=subclass_payload,
        name=subclass_payload.get("name"),
    )

    raw_spell_entities = {}
    for key, payload in spell_payloads.items():
        raw_entity, _, _ = upsert_raw_entity(
            session,
            source_id=source.id,
            entity_type="spell",
            source_key=key,
            payload=payload,
            name=payload.get("name"),
        )
        raw_spell_entities[key] = raw_entity

    raw_feature_entities = {}
    for key, payload in feature_payloads.items():
        raw_entity, _, _ = upsert_raw_entity(
            session,
            source_id=source.id,
            entity_type="feature",
            source_key=key,
            payload=payload,
            name=payload.get("name"),
        )
        raw_feature_entities[key] = raw_entity

    fighter = DndClass(
        source_id=source.id,
        raw_entity_id=raw_class_entities["fighter"].id,
        source_key="fighter",
        name="Fighter",
    )
    wizard = DndClass(
        source_id=source.id,
        raw_entity_id=raw_class_entities["wizard"].id,
        source_key="wizard",
        name="Wizard",
    )
    session.add(fighter)
    session.add(wizard)

    evocation = Subclass(
        source_id=source.id,
        raw_entity_id=raw_subclass.id,
        source_key="evocation",
        name="Evocation",
        class_source_key="wizard",
    )
    session.add(evocation)

    magic_missile = Spell(
        source_id=source.id,
        raw_entity_id=raw_spell_entities["magic-missile"].id,
        source_key="magic-missile",
        name="Magic Missile",
        level=1,
        concentration=False,
        ritual=False,
    )
    cure_wounds = Spell(
        source_id=source.id,
        raw_entity_id=raw_spell_entities["cure-wounds"].id,
        source_key="cure-wounds",
        name="Cure Wounds",
        level=1,
        concentration=False,
        ritual=False,
    )
    session.add(magic_missile)
    session.add(cure_wounds)

    fighting_style = Feature(
        source_id=source.id,
        raw_entity_id=raw_feature_entities["fighting-style"].id,
        source_key="fighting-style",
        name="Fighting Style",
        level=1,
        class_source_key="fighter",
    )
    sculpt_spells = Feature(
        source_id=source.id,
        raw_entity_id=raw_feature_entities["sculpt-spells"].id,
        source_key="sculpt-spells",
        name="Sculpt Spells",
        level=2,
        subclass_source_key="evocation",
    )
    session.add(fighting_style)
    session.add(sculpt_spells)
    session.commit()


def test_relationship_loader_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "relationships.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        _seed_relationship_data(session)

    summary = load_relationships(engine=engine, source_name="5e-bits")
    assert summary["spell_classes_created"] == 3
    assert summary["class_features_created"] == 1
    assert summary["subclass_features_created"] == 1

    with Session(engine) as session:
        spell_class_count = session.exec(
            select(func.count()).select_from(SpellClassLink)
        ).one()
        class_feature_count = session.exec(
            select(func.count()).select_from(ClassFeatureLink)
        ).one()
        subclass_feature_count = session.exec(
            select(func.count()).select_from(SubclassFeatureLink)
        ).one()
    assert spell_class_count == 3
    assert class_feature_count == 1
    assert subclass_feature_count == 1

    summary = load_relationships(engine=engine, source_name="5e-bits")
    assert summary["spell_classes_created"] == 0
    assert summary["class_features_created"] == 0
    assert summary["subclass_features_created"] == 0

    with Session(engine) as session:
        source = session.exec(select(Source).where(Source.name == "5e-bits")).one()
        updated_payload = {
            "index": "cure-wounds",
            "name": "Cure Wounds",
            "level": 1,
            "classes": [{"index": "wizard"}, {"index": "fighter"}],
        }
        upsert_raw_entity(
            session,
            source_id=source.id,
            entity_type="spell",
            source_key="cure-wounds",
            payload=updated_payload,
            name=updated_payload.get("name"),
        )

    summary = load_relationships(engine=engine, source_name="5e-bits")
    assert summary["spell_classes_created"] == 1

    with Session(engine) as session:
        spell_class_count = session.exec(
            select(func.count()).select_from(SpellClassLink)
        ).one()
    assert spell_class_count == 4
