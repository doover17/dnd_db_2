"""Character progression helpers."""

from __future__ import annotations

from typing import Iterable

from sqlmodel import Session, select

from dnd_db.models.character import CharacterChoice, CharacterFeature, CharacterLevel
from dnd_db.models.choices import ChoiceGroup, ChoiceOption, Prerequisite
from dnd_db.models.dnd_class import DndClass
from dnd_db.models.feature import Feature
from dnd_db.models.subclass import Subclass


def _compare_int(operator: str, left: int, right: int) -> bool:
    if operator == ">=":
        return left >= right
    if operator == ">":
        return left > right
    if operator == "<=":
        return left <= right
    if operator == "<":
        return left < right
    if operator == "==":
        return left == right
    return False


def _validate_prereqs(
    session: Session,
    character_id: int,
    class_id: int,
    subclass_id: int | None,
    level: int,
    prereqs: Iterable[Prerequisite],
    ability_scores: dict[str, int] | None,
) -> None:
    class_row = session.exec(select(DndClass).where(DndClass.id == class_id)).one()
    subclass_key = None
    if subclass_id is not None:
        subclass = session.exec(
            select(Subclass).where(Subclass.id == subclass_id)
        ).one_or_none()
        subclass_key = subclass.source_key if subclass else None

    feature_ids = {
        entry.feature_id
        for entry in session.exec(
            select(CharacterFeature).where(
                CharacterFeature.character_id == character_id
            )
        ).all()
    }

    for prereq in prereqs:
        if prereq.prereq_type == "class":
            if prereq.key != class_row.source_key:
                raise ValueError(f"Prerequisite failed: class {prereq.key}")
        elif prereq.prereq_type == "subclass":
            if subclass_key is None or prereq.key != subclass_key:
                raise ValueError(f"Prerequisite failed: subclass {prereq.key}")
        elif prereq.prereq_type == "feature":
            feature = session.exec(
                select(Feature).where(Feature.source_key == prereq.key)
            ).one_or_none()
            if feature is None or feature.id not in feature_ids:
                raise ValueError(f"Prerequisite failed: feature {prereq.key}")
        elif prereq.prereq_type == "level":
            if prereq.key not in ("any", class_row.source_key):
                raise ValueError(f"Prerequisite failed: level class {prereq.key}")
            if not _compare_int(prereq.operator, level, int(prereq.value)):
                raise ValueError(
                    f"Prerequisite failed: level {prereq.operator} {prereq.value}"
                )
        elif prereq.prereq_type == "ability":
            if ability_scores is None:
                raise ValueError(f"Prerequisite failed: ability {prereq.key}")
            score = ability_scores.get(prereq.key)
            if score is None or not _compare_int(
                prereq.operator, score, int(prereq.value)
            ):
                raise ValueError(f"Prerequisite failed: ability {prereq.key}")
        else:
            raise ValueError(f"Unsupported prerequisite type: {prereq.prereq_type}")


def apply_level_up(
    session: Session,
    *,
    character_id: int,
    class_id: int,
    level: int,
    subclass_id: int | None = None,
    choices: list[dict[str, int | str | None]] | None = None,
    ability_scores: dict[str, int] | None = None,
) -> CharacterLevel:
    """Record a level-up with optional choice selections."""
    existing = session.exec(
        select(CharacterLevel).where(
            CharacterLevel.character_id == character_id,
            CharacterLevel.level == level,
        )
    ).one_or_none()
    if existing is not None:
        raise ValueError(f"Character already has level {level}.")

    level_row = CharacterLevel(
        character_id=character_id,
        class_id=class_id,
        subclass_id=subclass_id,
        level=level,
    )
    session.add(level_row)
    session.flush()

    if choices:
        for choice in choices:
            group_id = choice.get("choice_group_id")
            if group_id is None:
                raise ValueError("Choice missing choice_group_id.")
            group = session.exec(
                select(ChoiceGroup).where(ChoiceGroup.id == int(group_id))
            ).one()
            prereqs = session.exec(
                select(Prerequisite).where(
                    Prerequisite.applies_to_type == "choice_group",
                    Prerequisite.applies_to_id == group.id,
                )
            ).all()
            _validate_prereqs(
                session,
                character_id,
                class_id,
                subclass_id,
                level,
                prereqs,
                ability_scores,
            )

            option_id = choice.get("choice_option_id")
            option_label = choice.get("option_label")
            if option_id is not None:
                option = session.exec(
                    select(ChoiceOption).where(ChoiceOption.id == int(option_id))
                ).one_or_none()
                if option is None:
                    raise ValueError(f"Choice option not found: {option_id}")
                option_label = option.label
            session.add(
                CharacterChoice(
                    character_id=character_id,
                    choice_group_id=group.id,
                    choice_option_id=int(option_id) if option_id is not None else None,
                    option_label=str(option_label) if option_label else None,
                )
            )

    session.commit()
    session.refresh(level_row)
    return level_row
