"""Verification checks for imported data."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_
from sqlmodel import Session, select

from dnd_db.models.dnd_class import DndClass
from dnd_db.models.feature import Feature
from dnd_db.models.import_run import ImportRun
from dnd_db.models.raw_entity import RawEntity
from dnd_db.models.relationships import (
    ClassFeatureLink,
    SpellClassLink,
    SubclassFeatureLink,
)
from dnd_db.models.source import Source
from dnd_db.models.spell import Spell
from dnd_db.models.subclass import Subclass


def check_counts(session: Session) -> dict[str, Any]:
    """Return counts for core tables and warn on mismatches."""
    source_count = session.exec(select(func.count()).select_from(Source)).one()
    import_run_count = session.exec(select(func.count()).select_from(ImportRun)).one()
    raw_total = session.exec(select(func.count()).select_from(RawEntity)).one()
    raw_spells = session.exec(
        select(func.count()).select_from(RawEntity).where(RawEntity.entity_type == "spell")
    ).one()
    raw_classes = session.exec(
        select(func.count()).select_from(RawEntity).where(RawEntity.entity_type == "class")
    ).one()
    raw_subclasses = session.exec(
        select(func.count())
        .select_from(RawEntity)
        .where(RawEntity.entity_type == "subclass")
    ).one()
    raw_features = session.exec(
        select(func.count()).select_from(RawEntity).where(RawEntity.entity_type == "feature")
    ).one()
    spell_count = session.exec(select(func.count()).select_from(Spell)).one()
    class_count = session.exec(select(func.count()).select_from(DndClass)).one()
    subclass_count = session.exec(select(func.count()).select_from(Subclass)).one()
    feature_count = session.exec(select(func.count()).select_from(Feature)).one()
    class_feature_count = session.exec(
        select(func.count()).select_from(ClassFeatureLink)
    ).one()
    subclass_feature_count = session.exec(
        select(func.count()).select_from(SubclassFeatureLink)
    ).one()
    spell_class_count = session.exec(
        select(func.count()).select_from(SpellClassLink)
    ).one()

    warnings: list[str] = []
    if raw_spells != spell_count:
        warnings.append(
            f"Spell count mismatch: raw_entities spell={raw_spells} spells={spell_count}"
        )
    if raw_classes != class_count:
        warnings.append(
            "Class count mismatch: "
            f"raw_entities class={raw_classes} classes={class_count}"
        )
    if raw_subclasses != subclass_count:
        warnings.append(
            "Subclass count mismatch: "
            f"raw_entities subclass={raw_subclasses} subclasses={subclass_count}"
        )
    if raw_features != feature_count:
        warnings.append(
            "Feature count mismatch: "
            f"raw_entities feature={raw_features} features={feature_count}"
        )

    return {
        "sources": source_count,
        "import_runs": import_run_count,
        "raw_entities": raw_total,
        "raw_entities_spell": raw_spells,
        "raw_entities_class": raw_classes,
        "raw_entities_subclass": raw_subclasses,
        "raw_entities_feature": raw_features,
        "spells": spell_count,
        "classes": class_count,
        "subclasses": subclass_count,
        "features": feature_count,
        "class_features": class_feature_count,
        "subclass_features": subclass_feature_count,
        "spell_classes": spell_class_count,
        "warnings": warnings,
    }


def check_duplicates(session: Session) -> list[str]:
    """Detect duplicate rows that violate uniqueness intent."""
    problems: list[str] = []

    raw_duplicates = session.exec(
        select(
            RawEntity.source_id,
            RawEntity.entity_type,
            RawEntity.source_key,
            func.count().label("count"),
        )
        .group_by(RawEntity.source_id, RawEntity.entity_type, RawEntity.source_key)
        .having(func.count() > 1)
    ).all()
    for source_id, entity_type, source_key, count in raw_duplicates:
        problems.append(
            "Duplicate raw entity: "
            f"source_id={source_id} entity_type={entity_type} source_key={source_key} count={count}"
        )

    spell_duplicates = session.exec(
        select(
            Spell.source_id,
            Spell.source_key,
            func.count().label("count"),
        )
        .group_by(Spell.source_id, Spell.source_key)
        .having(func.count() > 1)
    ).all()
    for source_id, source_key, count in spell_duplicates:
        problems.append(
            f"Duplicate spell: source_id={source_id} source_key={source_key} count={count}"
        )

    class_duplicates = session.exec(
        select(
            DndClass.source_id,
            DndClass.source_key,
            func.count().label("count"),
        )
        .group_by(DndClass.source_id, DndClass.source_key)
        .having(func.count() > 1)
    ).all()
    for source_id, source_key, count in class_duplicates:
        problems.append(
            "Duplicate class: "
            f"source_id={source_id} source_key={source_key} count={count}"
        )

    subclass_duplicates = session.exec(
        select(
            Subclass.source_id,
            Subclass.source_key,
            func.count().label("count"),
        )
        .group_by(Subclass.source_id, Subclass.source_key)
        .having(func.count() > 1)
    ).all()
    for source_id, source_key, count in subclass_duplicates:
        problems.append(
            "Duplicate subclass: "
            f"source_id={source_id} source_key={source_key} count={count}"
        )

    feature_duplicates = session.exec(
        select(
            Feature.source_id,
            Feature.source_key,
            func.count().label("count"),
        )
        .group_by(Feature.source_id, Feature.source_key)
        .having(func.count() > 1)
    ).all()
    for source_id, source_key, count in feature_duplicates:
        problems.append(
            "Duplicate feature: "
            f"source_id={source_id} source_key={source_key} count={count}"
        )

    class_feature_duplicates = session.exec(
        select(
            ClassFeatureLink.source_id,
            ClassFeatureLink.class_id,
            ClassFeatureLink.feature_id,
            func.coalesce(ClassFeatureLink.level, -1).label("level_key"),
            func.count().label("count"),
        )
        .group_by(
            ClassFeatureLink.source_id,
            ClassFeatureLink.class_id,
            ClassFeatureLink.feature_id,
            func.coalesce(ClassFeatureLink.level, -1),
        )
        .having(func.count() > 1)
    ).all()
    for source_id, class_id, feature_id, level_key, count in class_feature_duplicates:
        problems.append(
            "Duplicate class feature link: "
            "source_id="
            f"{source_id} class_id={class_id} feature_id={feature_id} level={level_key} count={count}"
        )

    subclass_feature_duplicates = session.exec(
        select(
            SubclassFeatureLink.source_id,
            SubclassFeatureLink.subclass_id,
            SubclassFeatureLink.feature_id,
            func.coalesce(SubclassFeatureLink.level, -1).label("level_key"),
            func.count().label("count"),
        )
        .group_by(
            SubclassFeatureLink.source_id,
            SubclassFeatureLink.subclass_id,
            SubclassFeatureLink.feature_id,
            func.coalesce(SubclassFeatureLink.level, -1),
        )
        .having(func.count() > 1)
    ).all()
    for (
        source_id,
        subclass_id,
        feature_id,
        level_key,
        count,
    ) in subclass_feature_duplicates:
        problems.append(
            "Duplicate subclass feature link: "
            "source_id="
            f"{source_id} subclass_id={subclass_id} feature_id={feature_id} level={level_key} count={count}"
        )

    spell_class_duplicates = session.exec(
        select(
            SpellClassLink.source_id,
            SpellClassLink.spell_id,
            SpellClassLink.class_id,
            func.count().label("count"),
        )
        .group_by(
            SpellClassLink.source_id,
            SpellClassLink.spell_id,
            SpellClassLink.class_id,
        )
        .having(func.count() > 1)
    ).all()
    for source_id, spell_id, class_id, count in spell_class_duplicates:
        problems.append(
            "Duplicate spell class link: "
            f"source_id={source_id} spell_id={spell_id} class_id={class_id} count={count}"
        )

    return problems


def check_missing_links(session: Session) -> list[str]:
    """Detect records missing raw entity links."""
    problems: list[str] = []

    missing_raw_link = session.exec(
        select(Spell).where(Spell.raw_entity_id.is_(None))
    ).all()
    for spell in missing_raw_link:
        problems.append(
            f"Spell missing raw_entity_id: id={spell.id} source_key={spell.source_key}"
        )

    raw_ids = select(RawEntity.id)
    orphaned = session.exec(
        select(Spell).where(
            Spell.raw_entity_id.is_not(None),
            ~Spell.raw_entity_id.in_(raw_ids),
        )
    ).all()
    for spell in orphaned:
        problems.append(
            "Spell raw_entity_id missing raw entity: "
            f"id={spell.id} raw_entity_id={spell.raw_entity_id}"
        )

    raw_spell_ids = select(Spell.raw_entity_id).where(Spell.raw_entity_id.is_not(None))
    orphaned_raw_entities = session.exec(
        select(RawEntity).where(
            RawEntity.entity_type == "spell",
            ~RawEntity.id.in_(raw_spell_ids),
        )
    ).all()
    for raw_entity in orphaned_raw_entities:
        problems.append(
            "Raw entity spell missing spell link: "
            f"id={raw_entity.id} source_key={raw_entity.source_key}"
        )

    missing_class_link = session.exec(
        select(DndClass).where(DndClass.raw_entity_id.is_(None))
    ).all()
    for character_class in missing_class_link:
        problems.append(
            "Class missing raw_entity_id: "
            f"id={character_class.id} source_key={character_class.source_key}"
        )

    orphaned_class = session.exec(
        select(DndClass).where(
            DndClass.raw_entity_id.is_not(None),
            ~DndClass.raw_entity_id.in_(raw_ids),
        )
    ).all()
    for character_class in orphaned_class:
        problems.append(
            "Class raw_entity_id missing raw entity: "
            f"id={character_class.id} raw_entity_id={character_class.raw_entity_id}"
        )

    raw_class_ids = select(DndClass.raw_entity_id).where(
        DndClass.raw_entity_id.is_not(None)
    )
    orphaned_raw_classes = session.exec(
        select(RawEntity).where(
            RawEntity.entity_type == "class",
            ~RawEntity.id.in_(raw_class_ids),
        )
    ).all()
    for raw_entity in orphaned_raw_classes:
        problems.append(
            "Raw entity class missing class link: "
            f"id={raw_entity.id} source_key={raw_entity.source_key}"
        )

    missing_subclass_link = session.exec(
        select(Subclass).where(Subclass.raw_entity_id.is_(None))
    ).all()
    for subclass in missing_subclass_link:
        problems.append(
            "Subclass missing raw_entity_id: "
            f"id={subclass.id} source_key={subclass.source_key}"
        )

    orphaned_subclass = session.exec(
        select(Subclass).where(
            Subclass.raw_entity_id.is_not(None),
            ~Subclass.raw_entity_id.in_(raw_ids),
        )
    ).all()
    for subclass in orphaned_subclass:
        problems.append(
            "Subclass raw_entity_id missing raw entity: "
            f"id={subclass.id} raw_entity_id={subclass.raw_entity_id}"
        )

    raw_subclass_ids = select(Subclass.raw_entity_id).where(
        Subclass.raw_entity_id.is_not(None)
    )
    orphaned_raw_subclasses = session.exec(
        select(RawEntity).where(
            RawEntity.entity_type == "subclass",
            ~RawEntity.id.in_(raw_subclass_ids),
        )
    ).all()
    for raw_entity in orphaned_raw_subclasses:
        problems.append(
            "Raw entity subclass missing subclass link: "
            f"id={raw_entity.id} source_key={raw_entity.source_key}"
        )

    missing_feature_link = session.exec(
        select(Feature).where(Feature.raw_entity_id.is_(None))
    ).all()
    for feature in missing_feature_link:
        problems.append(
            "Feature missing raw_entity_id: "
            f"id={feature.id} source_key={feature.source_key}"
        )

    orphaned_feature = session.exec(
        select(Feature).where(
            Feature.raw_entity_id.is_not(None),
            ~Feature.raw_entity_id.in_(raw_ids),
        )
    ).all()
    for feature in orphaned_feature:
        problems.append(
            "Feature raw_entity_id missing raw entity: "
            f"id={feature.id} raw_entity_id={feature.raw_entity_id}"
        )

    raw_feature_ids = select(Feature.raw_entity_id).where(
        Feature.raw_entity_id.is_not(None)
    )
    orphaned_raw_features = session.exec(
        select(RawEntity).where(
            RawEntity.entity_type == "feature",
            ~RawEntity.id.in_(raw_feature_ids),
        )
    ).all()
    for raw_entity in orphaned_raw_features:
        problems.append(
            "Raw entity feature missing feature link: "
            f"id={raw_entity.id} source_key={raw_entity.source_key}"
        )

    return problems


def check_relationship_integrity(session: Session) -> list[str]:
    """Detect missing or mismatched relationship references."""
    problems: list[str] = []

    missing_class_links = session.exec(
        select(ClassFeatureLink).where(
            ~ClassFeatureLink.class_id.in_(select(DndClass.id))
        )
    ).all()
    for link in missing_class_links:
        problems.append(
            "Class feature link missing class: "
            f"id={link.id} class_id={link.class_id}"
        )

    missing_feature_links = session.exec(
        select(ClassFeatureLink).where(
            ~ClassFeatureLink.feature_id.in_(select(Feature.id))
        )
    ).all()
    for link in missing_feature_links:
        problems.append(
            "Class feature link missing feature: "
            f"id={link.id} feature_id={link.feature_id}"
        )

    missing_subclass_links = session.exec(
        select(SubclassFeatureLink).where(
            ~SubclassFeatureLink.subclass_id.in_(select(Subclass.id))
        )
    ).all()
    for link in missing_subclass_links:
        problems.append(
            "Subclass feature link missing subclass: "
            f"id={link.id} subclass_id={link.subclass_id}"
        )

    missing_subclass_feature_links = session.exec(
        select(SubclassFeatureLink).where(
            ~SubclassFeatureLink.feature_id.in_(select(Feature.id))
        )
    ).all()
    for link in missing_subclass_feature_links:
        problems.append(
            "Subclass feature link missing feature: "
            f"id={link.id} feature_id={link.feature_id}"
        )

    missing_spell_class_links = session.exec(
        select(SpellClassLink).where(~SpellClassLink.spell_id.in_(select(Spell.id)))
    ).all()
    for link in missing_spell_class_links:
        problems.append(
            "Spell class link missing spell: "
            f"id={link.id} spell_id={link.spell_id}"
        )

    missing_spell_class_links = session.exec(
        select(SpellClassLink).where(~SpellClassLink.class_id.in_(select(DndClass.id)))
    ).all()
    for link in missing_spell_class_links:
        problems.append(
            "Spell class link missing class: "
            f"id={link.id} class_id={link.class_id}"
        )

    mismatched_class_features = session.exec(
        select(ClassFeatureLink, DndClass, Feature)
        .join(DndClass, ClassFeatureLink.class_id == DndClass.id)
        .join(Feature, ClassFeatureLink.feature_id == Feature.id)
        .where(
            (ClassFeatureLink.source_id != DndClass.source_id)
            | (ClassFeatureLink.source_id != Feature.source_id)
        )
    ).all()
    for link, dnd_class, feature in mismatched_class_features:
        problems.append(
            "Class feature link source mismatch: "
            "link_id="
            f"{link.id} link_source={link.source_id} "
            f"class_source={dnd_class.source_id} feature_source={feature.source_id}"
        )

    mismatched_subclass_features = session.exec(
        select(SubclassFeatureLink, Subclass, Feature)
        .join(Subclass, SubclassFeatureLink.subclass_id == Subclass.id)
        .join(Feature, SubclassFeatureLink.feature_id == Feature.id)
        .where(
            (SubclassFeatureLink.source_id != Subclass.source_id)
            | (SubclassFeatureLink.source_id != Feature.source_id)
        )
    ).all()
    for link, subclass, feature in mismatched_subclass_features:
        problems.append(
            "Subclass feature link source mismatch: "
            "link_id="
            f"{link.id} link_source={link.source_id} "
            f"subclass_source={subclass.source_id} feature_source={feature.source_id}"
        )

    mismatched_spell_classes = session.exec(
        select(SpellClassLink, Spell, DndClass)
        .join(Spell, SpellClassLink.spell_id == Spell.id)
        .join(DndClass, SpellClassLink.class_id == DndClass.id)
        .where(
            (SpellClassLink.source_id != Spell.source_id)
            | (SpellClassLink.source_id != DndClass.source_id)
        )
    ).all()
    for link, spell, dnd_class in mismatched_spell_classes:
        problems.append(
            "Spell class link source mismatch: "
            "link_id="
            f"{link.id} link_source={link.source_id} "
            f"spell_source={spell.source_id} class_source={dnd_class.source_id}"
        )

    return problems


def check_relationship_coverage(session: Session) -> list[str]:
    """Validate relationship counts when source entities exist."""
    problems: list[str] = []
    spell_count = session.exec(select(func.count()).select_from(Spell)).one()
    class_count = session.exec(select(func.count()).select_from(DndClass)).one()
    spell_class_count = session.exec(
        select(func.count()).select_from(SpellClassLink)
    ).one()
    if spell_count > 0 and class_count > 0 and spell_class_count == 0:
        problems.append(
            "Spell class coverage missing: spells and classes exist but spell_classes is empty"
        )

    feature_with_class_refs = session.exec(
        select(func.count())
        .select_from(Feature)
        .where(Feature.class_source_key.is_not(None))
    ).one()
    class_feature_count = session.exec(
        select(func.count()).select_from(ClassFeatureLink)
    ).one()
    if feature_with_class_refs > 0 and class_count > 0 and class_feature_count == 0:
        problems.append(
            "Class feature coverage missing: features reference classes but class_features is empty"
        )

    return problems


def check_spell_essentials(session: Session) -> list[str]:
    """Detect spells missing required name/index/level information."""
    problems: list[str] = []

    missing_essentials = session.exec(
        select(Spell).where(
            or_(
                Spell.name.is_(None),
                Spell.name == "",
                Spell.source_key.is_(None),
                Spell.source_key == "",
                Spell.level.is_(None),
            )
        )
    ).all()
    for spell in missing_essentials:
        problems.append(
            "Spell missing essentials: "
            f"id={spell.id} name={spell.name} source_key={spell.source_key} level={spell.level}"
        )

    return problems


def check_class_essentials(session: Session) -> list[str]:
    """Detect classes missing required name/index information."""
    problems: list[str] = []

    missing_essentials = session.exec(
        select(DndClass).where(
            or_(
                DndClass.name.is_(None),
                DndClass.name == "",
                DndClass.source_key.is_(None),
                DndClass.source_key == "",
            )
        )
    ).all()
    for character_class in missing_essentials:
        problems.append(
            "Class missing essentials: "
            f"id={character_class.id} name={character_class.name} source_key={character_class.source_key}"
        )

    return problems


def check_subclass_essentials(session: Session) -> list[str]:
    """Detect subclasses missing required name/index information."""
    problems: list[str] = []

    missing_essentials = session.exec(
        select(Subclass).where(
            or_(
                Subclass.name.is_(None),
                Subclass.name == "",
                Subclass.source_key.is_(None),
                Subclass.source_key == "",
            )
        )
    ).all()
    for subclass in missing_essentials:
        problems.append(
            "Subclass missing essentials: "
            f"id={subclass.id} name={subclass.name} source_key={subclass.source_key}"
        )

    return problems


def check_feature_essentials(session: Session) -> list[str]:
    """Detect features missing required name/index information."""
    problems: list[str] = []

    missing_essentials = session.exec(
        select(Feature).where(
            or_(
                Feature.name.is_(None),
                Feature.name == "",
                Feature.source_key.is_(None),
                Feature.source_key == "",
            )
        )
    ).all()
    for feature in missing_essentials:
        problems.append(
            "Feature missing essentials: "
            f"id={feature.id} name={feature.name} source_key={feature.source_key}"
        )

    return problems


def run_all_checks(session: Session) -> tuple[bool, dict[str, Any]]:
    """Run all verification checks and return (ok, report)."""
    counts = check_counts(session)
    warnings = counts.get("warnings", [])
    errors: list[str] = []

    if counts["raw_entities_spell"] != counts["spells"]:
        errors.append(
            "Spell count mismatch: "
            f"raw_entities spell={counts['raw_entities_spell']} spells={counts['spells']}"
        )
    if counts["raw_entities_class"] != counts["classes"]:
        errors.append(
            "Class count mismatch: "
            f"raw_entities class={counts['raw_entities_class']} classes={counts['classes']}"
        )
    if counts["raw_entities_subclass"] != counts["subclasses"]:
        errors.append(
            "Subclass count mismatch: "
            "raw_entities subclass="
            f"{counts['raw_entities_subclass']} subclasses={counts['subclasses']}"
        )
    if counts["raw_entities_feature"] != counts["features"]:
        errors.append(
            "Feature count mismatch: "
            "raw_entities feature="
            f"{counts['raw_entities_feature']} features={counts['features']}"
        )

    errors.extend(check_duplicates(session))
    errors.extend(check_missing_links(session))
    errors.extend(check_relationship_integrity(session))
    errors.extend(check_relationship_coverage(session))
    errors.extend(check_spell_essentials(session))
    errors.extend(check_class_essentials(session))
    errors.extend(check_subclass_essentials(session))
    errors.extend(check_feature_essentials(session))

    report = {
        "counts": counts,
        "warnings": warnings,
        "errors": errors,
    }
    ok = len(errors) == 0
    return ok, report
