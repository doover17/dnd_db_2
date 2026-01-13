"""Verification checks for choices and prerequisites."""

from __future__ import annotations

from sqlmodel import Session, select

from dnd_db.models.choices import ChoiceGroup, ChoiceOption
from dnd_db.models.dnd_class import DndClass
from dnd_db.models.feature import Feature
from dnd_db.models.subclass import Subclass


def verify_choices(session: Session) -> dict[str, list[str]]:
    """Verify choice groups and options integrity."""
    errors: list[str] = []

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
        errors.append(
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

    missing_subclass_groups = session.exec(
        select(ChoiceGroup).where(
            ChoiceGroup.owner_type == "subclass",
            ~ChoiceGroup.owner_id.in_(select(Subclass.id)),
        )
    ).all()
    for group in missing_subclass_groups:
        errors.append(
            "Choice group missing subclass owner: "
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

    return {"errors": errors}
