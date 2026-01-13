from __future__ import annotations

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from sqlmodel import Session

from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.models.choices import ChoiceGroup, ChoiceOption
from dnd_db.models.dnd_class import DndClass
from dnd_db.models.feature import Feature
from dnd_db.models.spell import Spell
from dnd_db.models.source import Source
from dnd_db.verify.choices import verify_choices


def test_verify_choices_passes(tmp_path: Path) -> None:
    db_path = tmp_path / "choices-verify.db"
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

        defense = Feature(
            source_id=source.id,
            raw_entity_id=None,
            source_key="fighting-style-defense",
            name="Defense",
            level=1,
            class_source_key="fighter",
        )
        session.add(defense)
        session.commit()
        session.refresh(defense)

        group = ChoiceGroup(
            source_id=source.id,
            owner_type="class",
            owner_id=fighter.id,
            choice_type="fighting_style",
            choose_n=1,
            level=1,
            label="Fighting Style",
            source_key="class:fighter:fighting_style:1:fighting-style",
        )
        session.add(group)
        session.commit()
        session.refresh(group)

        session.add(
            ChoiceOption(
                choice_group_id=group.id,
                option_type="feature",
                option_source_key="fighting-style-defense",
                label="Defense",
                feature_id=defense.id,
            )
        )
        session.commit()

        report = verify_choices(session)

    assert report["errors"] == []


def test_verify_choices_missing_spell(tmp_path: Path) -> None:
    db_path = tmp_path / "choices-verify-missing-spell.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        source = Source(name="5e-bits", base_url="https://example.com")
        session.add(source)
        session.commit()
        session.refresh(source)

        wizard = DndClass(
            source_id=source.id,
            raw_entity_id=None,
            source_key="wizard",
            name="Wizard",
        )
        session.add(wizard)
        session.commit()
        session.refresh(wizard)

        group = ChoiceGroup(
            source_id=source.id,
            owner_type="class",
            owner_id=wizard.id,
            choice_type="spell",
            choose_n=1,
            level=1,
            label="Spell Choice",
            source_key="class:wizard:spell:1:spell-choice",
        )
        session.add(group)
        session.commit()
        session.refresh(group)

        session.add(
            ChoiceOption(
                choice_group_id=group.id,
                option_type="spell",
                option_source_key="missing-spell",
                label="Missing Spell",
            )
        )
        session.commit()

        report = verify_choices(session)

    assert any("Choice option missing spell" in error for error in report["errors"])


def test_verify_choices_spell_ok(tmp_path: Path) -> None:
    db_path = tmp_path / "choices-verify-spell-ok.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        source = Source(name="5e-bits", base_url="https://example.com")
        session.add(source)
        session.commit()
        session.refresh(source)

        wizard = DndClass(
            source_id=source.id,
            raw_entity_id=None,
            source_key="wizard",
            name="Wizard",
        )
        session.add(wizard)
        session.commit()
        session.refresh(wizard)

        spell = Spell(
            source_id=source.id,
            raw_entity_id=None,
            source_key="magic-missile",
            name="Magic Missile",
            level=1,
        )
        session.add(spell)
        session.commit()

        group = ChoiceGroup(
            source_id=source.id,
            owner_type="class",
            owner_id=wizard.id,
            choice_type="spell",
            choose_n=1,
            level=1,
            label="Spell Choice",
            source_key="class:wizard:spell:1:spell-choice",
        )
        session.add(group)
        session.commit()
        session.refresh(group)

        session.add(
            ChoiceOption(
                choice_group_id=group.id,
                option_type="spell",
                option_source_key="magic-missile",
                label="Magic Missile",
            )
        )
        session.commit()

        report = verify_choices(session)

    assert report["errors"] == []
