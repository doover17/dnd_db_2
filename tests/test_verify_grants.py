from __future__ import annotations

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from sqlmodel import Session

from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.models.dnd_class import DndClass
from dnd_db.models.feature import Feature
from dnd_db.models.grants import GrantFeature, GrantProficiency, GrantSpell
from dnd_db.models.source import Source
from dnd_db.models.spell import Spell
from dnd_db.verify.grants import verify_grants


def test_verify_grants_passes(tmp_path: Path) -> None:
    db_path = tmp_path / "grants-verify.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        source = Source(name="5e-bits", base_url="https://example.com")
        session.add(source)
        session.commit()
        session.refresh(source)

        fighter = DndClass(
            source_id=source.id,
            raw_entity_id=None,
            source_key="fighter",
            name="Fighter",
        )
        session.add(fighter)
        session.commit()
        session.refresh(fighter)

        second_wind = Feature(
            source_id=source.id,
            raw_entity_id=None,
            source_key="second-wind",
            name="Second Wind",
            level=1,
            class_source_key="fighter",
        )
        session.add(second_wind)
        session.commit()

        spell = Spell(
            source_id=source.id,
            raw_entity_id=None,
            source_key="magic-missile",
            name="Magic Missile",
            level=1,
        )
        session.add(spell)
        session.commit()

        session.add(
            GrantProficiency(
                source_id=source.id,
                owner_type="class",
                owner_id=fighter.id,
                proficiency_type="starting_proficiencies",
                proficiency_key="armor-light",
                label="Light Armor",
            )
        )
        session.add(
            GrantSpell(
                source_id=source.id,
                owner_type="class",
                owner_id=fighter.id,
                spell_source_key="magic-missile",
                label="Magic Missile",
                spell_id=spell.id,
            )
        )
        session.add(
            GrantFeature(
                source_id=source.id,
                owner_type="class",
                owner_id=fighter.id,
                feature_source_key="second-wind",
                label="Second Wind",
                feature_id=second_wind.id,
            )
        )
        session.commit()

        report = verify_grants(session)

    assert report["errors"] == []


def test_verify_grants_missing_spell(tmp_path: Path) -> None:
    db_path = tmp_path / "grants-verify-missing.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        source = Source(name="5e-bits", base_url="https://example.com")
        session.add(source)
        session.commit()
        session.refresh(source)

        fighter = DndClass(
            source_id=source.id,
            raw_entity_id=None,
            source_key="fighter",
            name="Fighter",
        )
        session.add(fighter)
        session.commit()
        session.refresh(fighter)

        session.add(
            GrantSpell(
                source_id=source.id,
                owner_type="class",
                owner_id=fighter.id,
                spell_source_key="missing-spell",
                label="Missing Spell",
            )
        )
        session.commit()

        report = verify_grants(session)

    assert any("Grant spell missing spell reference" in error for error in report["errors"])
