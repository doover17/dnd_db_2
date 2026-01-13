"""Verification checks for choices."""

from __future__ import annotations

from sqlmodel import Session, select
from sqlalchemy import func

from dnd_db.models.choices import ChoiceGroup, ChoiceOption
from dnd_db.models.dnd_class import DndClass
from dnd_db.models.feature import Feature


def verify_choices(session: Session) -> dict[str, list[str]]:
    """Verify choice groups and options integrity."""
    errors: list[str] = []
    warnings: list[str] = []

    duplicate_groups = session.exec(
        select(
            ChoiceGroup.source_id,
            ChoiceGroup.owner_type,
            ChoiceGroup.owner_id,
            ChoiceGroup.choice_type,
            ChoiceGroup.level,
            ChoiceGroup.source_key,
            func.count(ChoiceGroup.id),
        ).group_by(
            ChoiceGroup.source_id,
            ChoiceGroup.owner_type,
            ChoiceGroup.owner_id,
            ChoiceGroup.choice_type,
            ChoiceGroup.level,
            ChoiceGroup.source_key,
        ).having(func.count(ChoiceGroup.id) > 1)
    ).all()
    for (
        source_id,
        owner_type,
        owner_id,
        choice_type,
        level,
        source_key,
        count,
    ) in duplicate_groups:
        errors.append(
            "Duplicate choice group: "
            f"source_id={source_id} owner_type={owner_type} owner_id={owner_id} "
            f"choice_type={choice_type} level={level} source_key={source_key} "
            f"count={count}"
        )

    duplicate_options = session.exec(
        select(
            ChoiceOption.choice_group_id,
            ChoiceOption.option_type,
            ChoiceOption.option_source_key,
            ChoiceOption.label,
            func.count(ChoiceOption.id),
        ).group_by(
            ChoiceOption.choice_group_id,
            ChoiceOption.option_type,
            ChoiceOption.option_source_key,
            ChoiceOption.label,
        ).having(func.count(ChoiceOption.id) > 1)
    ).all()
    for (
        choice_group_id,
        option_type,
        option_source_key,
        label,
        count,
    ) in duplicate_options:
        errors.append(
            "Duplicate choice option: "
            f"group_id={choice_group_id} option_type={option_type} "
            f"option_source_key={option_source_key} label={label} count={count}"
        )

    orphaned_options = session.exec(
        select(ChoiceOption).where(
            ~ChoiceOption.choice_group_id.in_(select(ChoiceGroup.id))
        )
    ).all()
    for option in orphaned_options:
        errors.append(
            "Choice option missing group: "
            f"id={option.id} choice_group_id={option.choice_group_id}"
        )

    empty_groups = session.exec(
        select(ChoiceGroup).where(
            ~ChoiceGroup.id.in_(select(ChoiceOption.choice_group_id))
        )
    ).all()
    for group in empty_groups:
        warnings.append(
            "Choice group has no options: "
            f"id={group.id} owner_type={group.owner_type} owner_id={group.owner_id}"
        )

    missing_class_groups = session.exec(
        select(ChoiceGroup).where(
            ChoiceGroup.owner_type == "class",
            ~ChoiceGroup.owner_id.in_(select(DndClass.id)),
        )
    ).all()
    for group in missing_class_groups:
        errors.append(
            "Choice group missing class owner: "
            f"id={group.id} owner_id={group.owner_id}"
        )

    missing_feature_groups = session.exec(
        select(ChoiceGroup).where(
            ChoiceGroup.owner_type == "feature",
            ~ChoiceGroup.owner_id.in_(select(Feature.id)),
        )
    ).all()
    for group in missing_feature_groups:
        errors.append(
            "Choice group missing feature owner: "
            f"id={group.id} owner_id={group.owner_id}"
        )

    missing_feature_options = session.exec(
        select(ChoiceOption).where(
            ChoiceOption.feature_id.is_not(None),
            ~ChoiceOption.feature_id.in_(select(Feature.id)),
        )
    ).all()
    for option in missing_feature_options:
        errors.append(
            "Choice option missing feature: "
            f"id={option.id} feature_id={option.feature_id}"
        )

    return {"errors": errors, "warnings": warnings}
