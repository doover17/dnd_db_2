from __future__ import annotations

from pathlib import Path
import sys

from sqlmodel import Session, select

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from dnd_db.character_progression import apply_level_up
from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.models.character import Character, CharacterChoice, CharacterLevel
from dnd_db.models.choices import ChoiceGroup, ChoiceOption, Prerequisite
from dnd_db.models.dnd_class import DndClass
from dnd_db.models.source import Source


def test_apply_level_up_with_choice_prereq(tmp_path: Path) -> None:
    db_path = tmp_path / "progression.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        source = Source(name="5e-bits", base_url="https://example.com")
        session.add(source)
        session.commit()
        session.refresh(source)

        fighter = DndClass(
            source_id=source.id,
            source_key="fighter",
            name="Fighter",
        )
        session.add(fighter)
        session.commit()
        session.refresh(fighter)

        group = ChoiceGroup(
            source_id=source.id,
            owner_type="class",
            owner_id=fighter.id,
            choice_type="generic",
            choose_n=1,
            level=2,
            label="Skill Proficiency",
            source_key="class:fighter:generic:2:skill-proficiency",
        )
        session.add(group)
        session.commit()
        session.refresh(group)

        option = ChoiceOption(
            choice_group_id=group.id,
            option_type="string",
            option_source_key="athletics",
            label="Athletics",
        )
        session.add(option)
        session.commit()
        session.refresh(option)

        session.add(
            Prerequisite(
                applies_to_type="choice_group",
                applies_to_id=group.id,
                prereq_type="class",
                key="fighter",
                operator="==",
                value="true",
            )
        )
        session.commit()

        character = Character(name="Tamsin")
        session.add(character)
        session.commit()
        session.refresh(character)

        level_row = apply_level_up(
            session,
            character_id=character.id,
            class_id=fighter.id,
            level=2,
            choices=[
                {
                    "choice_group_id": group.id,
                    "choice_option_id": option.id,
                }
            ],
        )

        stored_level = session.exec(
            select(CharacterLevel).where(CharacterLevel.id == level_row.id)
        ).one()
        assert stored_level.level == 2

        stored_choice = session.exec(
            select(CharacterChoice).where(
                CharacterChoice.character_id == character.id
            )
        ).one()
        assert stored_choice.choice_option_id == option.id
