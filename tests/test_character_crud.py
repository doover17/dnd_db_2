from __future__ import annotations

from pathlib import Path
import sys

from sqlmodel import Session, select

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.models.character import (
    Character,
    CharacterChoice,
    CharacterFeature,
    CharacterKnownSpell,
    CharacterLevel,
    CharacterPreparedSpell,
    InventoryItem,
)
from dnd_db.models.choices import ChoiceGroup, ChoiceOption
from dnd_db.models.dnd_class import DndClass
from dnd_db.models.feature import Feature
from dnd_db.models.source import Source
from dnd_db.models.spell import Spell
from dnd_db.models.subclass import Subclass


def test_character_crud(tmp_path: Path) -> None:
    db_path = tmp_path / "character.db"
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

        champion = Subclass(
            source_id=source.id,
            source_key="champion",
            name="Champion",
            class_source_key="fighter",
        )
        session.add(champion)
        session.commit()
        session.refresh(champion)

        feature = Feature(
            source_id=source.id,
            source_key="second-wind",
            name="Second Wind",
            level=1,
            class_source_key="fighter",
        )
        session.add(feature)
        session.commit()
        session.refresh(feature)

        spell = Spell(
            source_id=source.id,
            source_key="magic-missile",
            name="Magic Missile",
            level=1,
        )
        session.add(spell)
        session.commit()
        session.refresh(spell)

        group = ChoiceGroup(
            source_id=source.id,
            owner_type="class",
            owner_id=fighter.id,
            choice_type="generic",
            choose_n=1,
            level=1,
            label="Skill",
            source_key="class:fighter:generic:1:skill",
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

        character = Character(name="Arden", notes="Test character")
        session.add(character)
        session.commit()
        session.refresh(character)

        session.add(
            CharacterLevel(
                character_id=character.id,
                class_id=fighter.id,
                subclass_id=champion.id,
                level=1,
            )
        )
        session.add(
            CharacterChoice(
                character_id=character.id,
                choice_group_id=group.id,
                choice_option_id=option.id,
                option_label="Athletics",
            )
        )
        session.add(
            CharacterFeature(
                character_id=character.id,
                feature_id=feature.id,
            )
        )
        session.add(
            CharacterKnownSpell(
                character_id=character.id,
                spell_id=spell.id,
            )
        )
        session.add(
            CharacterPreparedSpell(
                character_id=character.id,
                spell_id=spell.id,
            )
        )
        session.add(
            InventoryItem(
                character_id=character.id,
                name="Rope",
                quantity=1,
                notes="50 ft hempen",
            )
        )
        session.commit()

        stored = session.exec(
            select(Character).where(Character.id == character.id)
        ).one()
        assert stored.name == "Arden"

        levels = session.exec(
            select(CharacterLevel).where(CharacterLevel.character_id == character.id)
        ).all()
        assert len(levels) == 1
        assert levels[0].class_id == fighter.id

        choices = session.exec(
            select(CharacterChoice).where(CharacterChoice.character_id == character.id)
        ).all()
        assert len(choices) == 1
        assert choices[0].choice_option_id == option.id

        features = session.exec(
            select(CharacterFeature).where(CharacterFeature.character_id == character.id)
        ).all()
        assert len(features) == 1

        known_spells = session.exec(
            select(CharacterKnownSpell).where(
                CharacterKnownSpell.character_id == character.id
            )
        ).all()
        assert len(known_spells) == 1

        prepared_spells = session.exec(
            select(CharacterPreparedSpell).where(
                CharacterPreparedSpell.character_id == character.id
            )
        ).all()
        assert len(prepared_spells) == 1

        inventory = session.exec(
            select(InventoryItem).where(InventoryItem.character_id == character.id)
        ).all()
        assert len(inventory) == 1
