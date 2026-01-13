"""Derived query helpers for character-sheet-style questions."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlmodel import Session, select

from dnd_db.models.choices import ChoiceGroup, ChoiceOption
from dnd_db.models.feature import Feature
from dnd_db.models.relationships import (
    ClassFeatureLink,
    SpellClassLink,
    SubclassFeatureLink,
)
from dnd_db.models.spell import Spell


def _effective_level(feature: Feature, link_level: int | None) -> int | None:
    return link_level if link_level is not None else feature.level


def _feature_payload(feature: Feature, level: int | None) -> dict[str, Any]:
    return {
        "id": feature.id,
        "source_key": feature.source_key,
        "name": feature.name,
        "level": level,
        "desc": feature.desc,
    }


def get_class_features_at_level(
    session: Session,
    class_id: int,
    level: int,
) -> list[dict[str, Any]]:
    """Return class features available at the requested level."""
    rows = session.exec(
        select(Feature, ClassFeatureLink.level)
        .join(ClassFeatureLink, ClassFeatureLink.feature_id == Feature.id)
        .where(ClassFeatureLink.class_id == class_id)
    ).all()

    results: list[dict[str, Any]] = []
    for feature, link_level in rows:
        effective_level = _effective_level(feature, link_level)
        if effective_level == level:
            results.append(_feature_payload(feature, effective_level))

    results.sort(key=lambda item: (item["level"] or 0, item["name"], item["id"]))
    return results


def get_subclass_features_at_level(
    session: Session,
    subclass_id: int,
    level: int,
) -> list[dict[str, Any]]:
    """Return subclass features available at the requested level."""
    rows = session.exec(
        select(Feature, SubclassFeatureLink.level)
        .join(SubclassFeatureLink, SubclassFeatureLink.feature_id == Feature.id)
        .where(SubclassFeatureLink.subclass_id == subclass_id)
    ).all()

    results: list[dict[str, Any]] = []
    for feature, link_level in rows:
        effective_level = _effective_level(feature, link_level)
        if effective_level == level:
            results.append(_feature_payload(feature, effective_level))

    results.sort(key=lambda item: (item["level"] or 0, item["name"], item["id"]))
    return results


def get_spell_list_for_class(session: Session, class_id: int) -> list[dict[str, Any]]:
    """Return spell list for the requested class."""
    rows = session.exec(
        select(Spell)
        .join(SpellClassLink, SpellClassLink.spell_id == Spell.id)
        .where(SpellClassLink.class_id == class_id)
    ).all()

    results = [
        {
            "id": spell.id,
            "source_key": spell.source_key,
            "name": spell.name,
            "level": spell.level,
            "school": spell.school,
        }
        for spell in rows
    ]
    results.sort(key=lambda item: (item["level"], item["name"], item["id"]))
    return results


def get_choices_for_class_at_level(
    session: Session,
    class_id: int,
    level: int,
) -> list[dict[str, Any]]:
    """Return class choice groups and options at the requested level."""
    groups = session.exec(
        select(ChoiceGroup)
        .where(
            ChoiceGroup.owner_type == "class",
            ChoiceGroup.owner_id == class_id,
            ChoiceGroup.level == level,
        )
    ).all()
    if not groups:
        return []

    group_ids = [group.id for group in groups if group.id is not None]
    options = session.exec(
        select(ChoiceOption).where(ChoiceOption.choice_group_id.in_(group_ids))
    ).all()

    options_by_group: dict[int, list[ChoiceOption]] = defaultdict(list)
    for option in options:
        options_by_group[option.choice_group_id].append(option)

    results: list[dict[str, Any]] = []
    for group in groups:
        group_options = options_by_group.get(group.id or 0, [])
        group_options.sort(key=lambda option: (option.label, option.id or 0))
        results.append(
            {
                "id": group.id,
                "choice_type": group.choice_type,
                "choose_n": group.choose_n,
                "level": group.level,
                "label": group.label,
                "notes": group.notes,
                "source_key": group.source_key,
                "options": [
                    {
                        "id": option.id,
                        "option_type": option.option_type,
                        "option_source_key": option.option_source_key,
                        "feature_id": option.feature_id,
                        "label": option.label,
                    }
                    for option in group_options
                ],
            }
        )

    results.sort(key=lambda item: (item["level"] or 0, item["choice_type"], item["id"]))
    return results


def get_all_available_features(
    session: Session,
    class_id: int,
    subclass_id: int | None,
    level: int,
) -> dict[str, list[dict[str, Any]]]:
    """Return all class and subclass features unlocked at or below level."""
    class_rows = session.exec(
        select(Feature, ClassFeatureLink.level)
        .join(ClassFeatureLink, ClassFeatureLink.feature_id == Feature.id)
        .where(ClassFeatureLink.class_id == class_id)
    ).all()

    class_features: list[dict[str, Any]] = []
    for feature, link_level in class_rows:
        effective_level = _effective_level(feature, link_level)
        if effective_level is not None and effective_level <= level:
            class_features.append(_feature_payload(feature, effective_level))

    subclass_features: list[dict[str, Any]] = []
    if subclass_id is not None:
        subclass_rows = session.exec(
            select(Feature, SubclassFeatureLink.level)
            .join(SubclassFeatureLink, SubclassFeatureLink.feature_id == Feature.id)
            .where(SubclassFeatureLink.subclass_id == subclass_id)
        ).all()
        for feature, link_level in subclass_rows:
            effective_level = _effective_level(feature, link_level)
            if effective_level is not None and effective_level <= level:
                subclass_features.append(_feature_payload(feature, effective_level))

    class_features.sort(key=lambda item: (item["level"] or 0, item["name"], item["id"]))
    subclass_features.sort(
        key=lambda item: (item["level"] or 0, item["name"], item["id"])
    )

    return {
        "class_features": class_features,
        "subclass_features": subclass_features,
    }
