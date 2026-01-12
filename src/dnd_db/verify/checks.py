"""Verification checks for imported data."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_
from sqlmodel import Session, select

from dnd_db.models.import_run import ImportRun
from dnd_db.models.raw_entity import RawEntity
from dnd_db.models.source import Source
from dnd_db.models.spell import Spell


def check_counts(session: Session) -> dict[str, Any]:
    """Return counts for core tables and warn on mismatches."""
    source_count = session.exec(select(func.count()).select_from(Source)).one()
    import_run_count = session.exec(select(func.count()).select_from(ImportRun)).one()
    raw_total = session.exec(select(func.count()).select_from(RawEntity)).one()
    raw_spells = session.exec(
        select(func.count()).select_from(RawEntity).where(RawEntity.entity_type == "spell")
    ).one()
    spell_count = session.exec(select(func.count()).select_from(Spell)).one()

    warnings: list[str] = []
    if raw_spells != spell_count:
        warnings.append(
            f"Spell count mismatch: raw_entities spell={raw_spells} spells={spell_count}"
        )

    return {
        "sources": source_count,
        "import_runs": import_run_count,
        "raw_entities": raw_total,
        "raw_entities_spell": raw_spells,
        "spells": spell_count,
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

    return problems


def check_missing_links(session: Session) -> list[str]:
    """Detect spells missing raw entity links."""
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


def run_all_checks(session: Session) -> tuple[bool, dict[str, Any]]:
    """Run all verification checks and return (ok, report)."""
    counts = check_counts(session)
    problems: list[str] = []
    if counts["raw_entities_spell"] != counts["spells"]:
        problems.append(
            "Spell count mismatch: "
            f"raw_entities spell={counts['raw_entities_spell']} spells={counts['spells']}"
        )
    problems.extend(check_duplicates(session))
    problems.extend(check_missing_links(session))
    problems.extend(check_spell_essentials(session))

    report = {
        "counts": counts,
        "problems": problems,
    }
    ok = len(problems) == 0
    return ok, report
