"""Verification checks for imported data."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_
from sqlmodel import Session, select

from dnd_db.models.dnd_class import DndClass
from dnd_db.models.feature import Feature
from dnd_db.models.import_run import ImportRun
from dnd_db.models.raw_entity import RawEntity
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
