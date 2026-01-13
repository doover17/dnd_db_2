"""Snapshot creation and diff helpers."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Iterable

from sqlalchemy import func
from sqlmodel import Session, select

from dnd_db.models.choices import ChoiceGroup, ChoiceOption, Prerequisite
from dnd_db.models.condition import Condition
from dnd_db.models.grants import GrantFeature, GrantProficiency, GrantSpell
from dnd_db.models.import_run import ImportRun
from dnd_db.models.import_snapshot import ImportSnapshot
from dnd_db.models.item import Item
from dnd_db.models.monster import Monster
from dnd_db.models.raw_entity import RawEntity
from dnd_db.models.relationships import (
    ClassFeatureLink,
    SpellClassLink,
    SubclassFeatureLink,
)
from dnd_db.models.source import Source
from dnd_db.models.spell import Spell
from dnd_db.models.subclass import Subclass
from dnd_db.models.dnd_class import DndClass
from dnd_db.models.feature import Feature


def _hash_rows(rows: Iterable[Iterable[Any]]) -> str:
    normalized = [list(row) for row in rows]
    payload = json.dumps(normalized, sort_keys=True, default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


def _count(session: Session, statement) -> int:
    return int(session.exec(statement).one())


def _raw_hashes(session: Session, source_id: int, entity_type: str) -> str:
    rows = session.exec(
        select(RawEntity.source_key, RawEntity.raw_hash)
        .where(RawEntity.source_id == source_id, RawEntity.entity_type == entity_type)
        .order_by(RawEntity.source_key)
    ).all()
    return _hash_rows(rows)


def _table_hash(session: Session, statement) -> str:
    rows = session.exec(statement).all()
    return _hash_rows(rows)


def create_snapshot(session: Session, source_id: int) -> ImportSnapshot:
    """Create and store a snapshot for the source."""
    source = session.exec(select(Source).where(Source.id == source_id)).one()
    latest_run = session.exec(
        select(ImportRun)
        .where(ImportRun.source_id == source_id)
        .order_by(ImportRun.id.desc())
        .limit(1)
    ).one_or_none()
    run_key = latest_run.run_key if latest_run is not None else None

    counts: dict[str, int] = {
        "raw_entities": _count(
            session,
            select(func.count()).select_from(RawEntity).where(RawEntity.source_id == source_id),
        ),
        "spells": _count(
            session,
            select(func.count()).select_from(Spell).where(Spell.source_id == source_id),
        ),
        "classes": _count(
            session,
            select(func.count()).select_from(DndClass).where(DndClass.source_id == source_id),
        ),
        "subclasses": _count(
            session,
            select(func.count()).select_from(Subclass).where(Subclass.source_id == source_id),
        ),
        "features": _count(
            session,
            select(func.count()).select_from(Feature).where(Feature.source_id == source_id),
        ),
        "class_features": _count(
            session,
            select(func.count()).select_from(ClassFeatureLink).where(ClassFeatureLink.source_id == source_id),
        ),
        "subclass_features": _count(
            session,
            select(func.count()).select_from(SubclassFeatureLink).where(SubclassFeatureLink.source_id == source_id),
        ),
        "spell_classes": _count(
            session,
            select(func.count()).select_from(SpellClassLink).where(SpellClassLink.source_id == source_id),
        ),
        "choice_groups": _count(
            session,
            select(func.count()).select_from(ChoiceGroup).where(ChoiceGroup.source_id == source_id),
        ),
        "choice_options": _count(
            session,
            select(func.count())
            .select_from(ChoiceOption)
            .join(ChoiceGroup, ChoiceOption.choice_group_id == ChoiceGroup.id)
            .where(ChoiceGroup.source_id == source_id),
        ),
        "prerequisites": _count(
            session,
            select(func.count()).select_from(Prerequisite),
        ),
        "grant_proficiencies": _count(
            session,
            select(func.count()).select_from(GrantProficiency).where(GrantProficiency.source_id == source_id),
        ),
        "grant_spells": _count(
            session,
            select(func.count()).select_from(GrantSpell).where(GrantSpell.source_id == source_id),
        ),
        "grant_features": _count(
            session,
            select(func.count()).select_from(GrantFeature).where(GrantFeature.source_id == source_id),
        ),
        "items": _count(
            session,
            select(func.count()).select_from(Item).where(Item.source_id == source_id),
        ),
        "conditions": _count(
            session,
            select(func.count()).select_from(Condition).where(Condition.source_id == source_id),
        ),
        "monsters": _count(
            session,
            select(func.count()).select_from(Monster).where(Monster.source_id == source_id),
        ),
    }

    hashes: dict[str, str] = {
        "raw_entities": _table_hash(
            session,
            select(RawEntity.source_key, RawEntity.raw_hash)
            .where(RawEntity.source_id == source_id)
            .order_by(RawEntity.source_key),
        ),
        "raw_entities_spell": _raw_hashes(session, source_id, "spell"),
        "raw_entities_class": _raw_hashes(session, source_id, "class"),
        "raw_entities_subclass": _raw_hashes(session, source_id, "subclass"),
        "raw_entities_feature": _raw_hashes(session, source_id, "feature"),
        "raw_entities_equipment": _raw_hashes(session, source_id, "equipment"),
        "raw_entities_condition": _raw_hashes(session, source_id, "condition"),
        "raw_entities_monster": _raw_hashes(session, source_id, "monster"),
        "spells": _table_hash(
            session,
            select(Spell.source_key, Spell.raw_entity_id)
            .where(Spell.source_id == source_id)
            .order_by(Spell.source_key),
        ),
        "classes": _table_hash(
            session,
            select(DndClass.source_key, DndClass.raw_entity_id)
            .where(DndClass.source_id == source_id)
            .order_by(DndClass.source_key),
        ),
        "subclasses": _table_hash(
            session,
            select(Subclass.source_key, Subclass.raw_entity_id)
            .where(Subclass.source_id == source_id)
            .order_by(Subclass.source_key),
        ),
        "features": _table_hash(
            session,
            select(Feature.source_key, Feature.raw_entity_id)
            .where(Feature.source_id == source_id)
            .order_by(Feature.source_key),
        ),
        "items": _table_hash(
            session,
            select(Item.source_key, Item.raw_entity_id)
            .where(Item.source_id == source_id)
            .order_by(Item.source_key),
        ),
        "conditions": _table_hash(
            session,
            select(Condition.source_key, Condition.raw_entity_id)
            .where(Condition.source_id == source_id)
            .order_by(Condition.source_key),
        ),
        "monsters": _table_hash(
            session,
            select(Monster.source_key, Monster.raw_entity_id)
            .where(Monster.source_id == source_id)
            .order_by(Monster.source_key),
        ),
        "class_features": _table_hash(
            session,
            select(ClassFeatureLink.class_id, ClassFeatureLink.feature_id, ClassFeatureLink.level)
            .where(ClassFeatureLink.source_id == source_id)
            .order_by(ClassFeatureLink.class_id, ClassFeatureLink.feature_id),
        ),
        "subclass_features": _table_hash(
            session,
            select(SubclassFeatureLink.subclass_id, SubclassFeatureLink.feature_id, SubclassFeatureLink.level)
            .where(SubclassFeatureLink.source_id == source_id)
            .order_by(SubclassFeatureLink.subclass_id, SubclassFeatureLink.feature_id),
        ),
        "spell_classes": _table_hash(
            session,
            select(SpellClassLink.class_id, SpellClassLink.spell_id)
            .where(SpellClassLink.source_id == source_id)
            .order_by(SpellClassLink.class_id, SpellClassLink.spell_id),
        ),
        "choice_groups": _table_hash(
            session,
            select(
                ChoiceGroup.source_key,
                ChoiceGroup.choice_type,
                ChoiceGroup.level,
            )
            .where(ChoiceGroup.source_id == source_id)
            .order_by(ChoiceGroup.source_key),
        ),
        "choice_options": _table_hash(
            session,
            select(
                ChoiceOption.choice_group_id,
                ChoiceOption.option_type,
                ChoiceOption.option_source_key,
                ChoiceOption.label,
            )
            .join(ChoiceGroup, ChoiceOption.choice_group_id == ChoiceGroup.id)
            .where(ChoiceGroup.source_id == source_id)
            .order_by(ChoiceOption.choice_group_id, ChoiceOption.label),
        ),
        "prerequisites": _table_hash(
            session,
            select(
                Prerequisite.applies_to_type,
                Prerequisite.applies_to_id,
                Prerequisite.prereq_type,
                Prerequisite.key,
                Prerequisite.operator,
                Prerequisite.value,
            ).order_by(
                Prerequisite.applies_to_type,
                Prerequisite.applies_to_id,
                Prerequisite.prereq_type,
            ),
        ),
        "grant_proficiencies": _table_hash(
            session,
            select(
                GrantProficiency.owner_type,
                GrantProficiency.owner_id,
                GrantProficiency.proficiency_type,
                GrantProficiency.proficiency_key,
                GrantProficiency.label,
            )
            .where(GrantProficiency.source_id == source_id)
            .order_by(GrantProficiency.owner_type, GrantProficiency.proficiency_key),
        ),
        "grant_spells": _table_hash(
            session,
            select(
                GrantSpell.owner_type,
                GrantSpell.owner_id,
                GrantSpell.spell_source_key,
                GrantSpell.label,
            )
            .where(GrantSpell.source_id == source_id)
            .order_by(GrantSpell.owner_type, GrantSpell.spell_source_key),
        ),
        "grant_features": _table_hash(
            session,
            select(
                GrantFeature.owner_type,
                GrantFeature.owner_id,
                GrantFeature.feature_source_key,
                GrantFeature.label,
            )
            .where(GrantFeature.source_id == source_id)
            .order_by(GrantFeature.owner_type, GrantFeature.feature_source_key),
        ),
    }

    snapshot = ImportSnapshot(
        source_id=source.id,
        run_key=run_key,
        counts_json=json.dumps(counts, sort_keys=True),
        hashes_json=json.dumps(hashes, sort_keys=True),
    )
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)
    return snapshot


def diff_snapshots(
    older: ImportSnapshot | None, newer: ImportSnapshot
) -> dict[str, list[str]]:
    """Compare two snapshots and summarize differences."""
    changes: list[str] = []
    if older is None:
        return {"changes": ["No previous snapshot found."]}

    older_counts = json.loads(older.counts_json)
    newer_counts = json.loads(newer.counts_json)
    for key in sorted(set(older_counts) | set(newer_counts)):
        old_val = older_counts.get(key, 0)
        new_val = newer_counts.get(key, 0)
        if old_val != new_val:
            changes.append(f"Count {key}: {old_val} -> {new_val}")

    older_hashes = json.loads(older.hashes_json)
    newer_hashes = json.loads(newer.hashes_json)
    for key in sorted(set(older_hashes) | set(newer_hashes)):
        if older_hashes.get(key) != newer_hashes.get(key):
            changes.append(f"Hash {key} changed")

    if not changes:
        changes.append("No changes detected.")
    return {"changes": changes}
