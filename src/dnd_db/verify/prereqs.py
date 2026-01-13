"""Verification checks for prerequisites."""

from __future__ import annotations

from sqlmodel import Session, select
from sqlalchemy import func

from dnd_db.models.choices import ChoiceGroup, Prerequisite
from dnd_db.models.dnd_class import DndClass
from dnd_db.models.feature import Feature
from dnd_db.models.subclass import Subclass


def verify_prereqs(session: Session) -> dict[str, list[str]]:
    """Verify prerequisite integrity."""
    errors: list[str] = []
    warnings: list[str] = []

    duplicate_prereqs = session.exec(
        select(
            Prerequisite.applies_to_type,
            Prerequisite.applies_to_id,
            Prerequisite.prereq_type,
            Prerequisite.key,
            Prerequisite.operator,
            Prerequisite.value,
            func.count(Prerequisite.id),
        )
        .group_by(
            Prerequisite.applies_to_type,
            Prerequisite.applies_to_id,
            Prerequisite.prereq_type,
            Prerequisite.key,
            Prerequisite.operator,
            Prerequisite.value,
        )
        .having(func.count(Prerequisite.id) > 1)
    ).all()
    for (
        applies_to_type,
        applies_to_id,
        prereq_type,
        key,
        operator,
        value,
        count,
    ) in duplicate_prereqs:
        errors.append(
            "Duplicate prerequisite: "
            f"applies_to_type={applies_to_type} applies_to_id={applies_to_id} "
            f"prereq_type={prereq_type} key={key} operator={operator} value={value} "
            f"count={count}"
        )

    missing_feature_applies_to = session.exec(
        select(Prerequisite).where(
            Prerequisite.applies_to_type == "feature",
            ~Prerequisite.applies_to_id.in_(select(Feature.id)),
        )
    ).all()
    for prereq in missing_feature_applies_to:
        errors.append(
            "Prerequisite missing feature apply target: "
            f"id={prereq.id} applies_to_id={prereq.applies_to_id}"
        )

    missing_choice_group_applies_to = session.exec(
        select(Prerequisite).where(
            Prerequisite.applies_to_type == "choice_group",
            ~Prerequisite.applies_to_id.in_(select(ChoiceGroup.id)),
        )
    ).all()
    for prereq in missing_choice_group_applies_to:
        errors.append(
            "Prerequisite missing choice group apply target: "
            f"id={prereq.id} applies_to_id={prereq.applies_to_id}"
        )

    missing_class_refs = session.exec(
        select(Prerequisite)
        .join(Feature, Prerequisite.applies_to_id == Feature.id)
        .where(
            Prerequisite.applies_to_type == "feature",
            Prerequisite.prereq_type == "class",
            ~Prerequisite.key.in_(select(DndClass.source_key)),
        )
    ).all()
    for prereq in missing_class_refs:
        errors.append(
            "Prerequisite missing class reference: "
            f"id={prereq.id} key={prereq.key}"
        )

    missing_subclass_refs = session.exec(
        select(Prerequisite)
        .join(Feature, Prerequisite.applies_to_id == Feature.id)
        .where(
            Prerequisite.applies_to_type == "feature",
            Prerequisite.prereq_type == "subclass",
            ~Prerequisite.key.in_(select(Subclass.source_key)),
        )
    ).all()
    for prereq in missing_subclass_refs:
        errors.append(
            "Prerequisite missing subclass reference: "
            f"id={prereq.id} key={prereq.key}"
        )

    missing_feature_refs = session.exec(
        select(Prerequisite)
        .join(Feature, Prerequisite.applies_to_id == Feature.id)
        .where(
            Prerequisite.applies_to_type == "feature",
            Prerequisite.prereq_type == "feature",
            ~Prerequisite.key.in_(select(Feature.source_key)),
        )
    ).all()
    for prereq in missing_feature_refs:
        errors.append(
            "Prerequisite missing feature reference: "
            f"id={prereq.id} key={prereq.key}"
        )

    missing_class_refs_for_group = session.exec(
        select(Prerequisite)
        .join(ChoiceGroup, Prerequisite.applies_to_id == ChoiceGroup.id)
        .where(
            Prerequisite.applies_to_type == "choice_group",
            Prerequisite.prereq_type == "class",
            ~Prerequisite.key.in_(select(DndClass.source_key)),
        )
    ).all()
    for prereq in missing_class_refs_for_group:
        errors.append(
            "Prerequisite missing class reference: "
            f"id={prereq.id} key={prereq.key}"
        )

    missing_subclass_refs_for_group = session.exec(
        select(Prerequisite)
        .join(ChoiceGroup, Prerequisite.applies_to_id == ChoiceGroup.id)
        .where(
            Prerequisite.applies_to_type == "choice_group",
            Prerequisite.prereq_type == "subclass",
            ~Prerequisite.key.in_(select(Subclass.source_key)),
        )
    ).all()
    for prereq in missing_subclass_refs_for_group:
        errors.append(
            "Prerequisite missing subclass reference: "
            f"id={prereq.id} key={prereq.key}"
        )

    missing_feature_refs_for_group = session.exec(
        select(Prerequisite)
        .join(ChoiceGroup, Prerequisite.applies_to_id == ChoiceGroup.id)
        .where(
            Prerequisite.applies_to_type == "choice_group",
            Prerequisite.prereq_type == "feature",
            ~Prerequisite.key.in_(select(Feature.source_key)),
        )
    ).all()
    for prereq in missing_feature_refs_for_group:
        errors.append(
            "Prerequisite missing feature reference: "
            f"id={prereq.id} key={prereq.key}"
        )

    return {"errors": errors, "warnings": warnings}
