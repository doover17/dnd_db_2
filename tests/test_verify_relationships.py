from __future__ import annotations

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from sqlmodel import Session, select

from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.ingest.load_relationships import load_relationships
from dnd_db.models.relationships import SpellClassLink
from dnd_db.models.source import Source
from dnd_db.db.upsert import upsert_raw_entity
from dnd_db.models.dnd_class import DndClass
from dnd_db.models.feature import Feature
from dnd_db.models.spell import Spell
from dnd_db.models.subclass import Subclass
from dnd_db.verify.checks import run_all_checks


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


def test_verify_relationships_ok(tmp_path: Path) -> None:
    db_path = tmp_path / "verify_relationships.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        _seed_relationship_data(session)

    load_relationships(engine=engine, source_name="5e-bits")
    with Session(engine) as session:
        ok, report = run_all_checks(session)

    assert ok is True
    assert report["errors"] == []


def test_verify_relationships_detects_mismatch(tmp_path: Path) -> None:
    db_path = tmp_path / "verify_relationships_mismatch.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        _seed_relationship_data(session)

    load_relationships(engine=engine, source_name="5e-bits")

    with Session(engine) as session:
        source = session.exec(select(Source).where(Source.name == "5e-bits")).one()
        other_source = Source(name="other-source")
        session.add(other_source)
        session.commit()
        session.refresh(other_source)
        link = session.exec(select(SpellClassLink)).first()
        assert link is not None
        bad_link = SpellClassLink(
            source_id=other_source.id,
            spell_id=link.spell_id,
            class_id=link.class_id,
        )
        session.add(bad_link)
        session.commit()

    with Session(engine) as session:
        ok, report = run_all_checks(session)

    assert ok is False
    assert any("source mismatch" in error for error in report["errors"])
