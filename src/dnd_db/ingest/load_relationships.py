"""Relationship loader pipeline."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from dnd_db.db.engine import create_db_and_tables
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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _source_or_raise(session: Session, source_name: str) -> Source:
    source = session.exec(select(Source).where(Source.name == source_name)).one_or_none()
    if source is None:
        raise ValueError("Run importers first: source not found.")
    return source


def _extract_class_indices(payload: dict[str, Any]) -> list[str]:
    classes = payload.get("classes")
    if classes is None:
        classes = payload.get("class")
    if isinstance(classes, dict):
        index = classes.get("index")
        return [index] if index else []
    if isinstance(classes, list):
        results: list[str] = []
        for entry in classes:
            if isinstance(entry, dict):
                index = entry.get("index")
                if index:
                    results.append(index)
        return results
    return []


def _extract_feature_refs(payload: dict[str, Any]) -> tuple[str | None, str | None, int | None]:
    class_info = payload.get("class")
    subclass_info = payload.get("subclass")
    class_index = class_info.get("index") if isinstance(class_info, dict) else None
    subclass_index = (
        subclass_info.get("index") if isinstance(subclass_info, dict) else None
    )
    level = payload.get("level")
    if level is not None:
        try:
            level = int(level)
        except (TypeError, ValueError):
            level = None
    return class_index, subclass_index, level


def _level_key(level: int | None) -> int:
    return level if level is not None else -1


def load_relationships(*, engine, source_name: str = "5e-bits") -> dict[str, int]:
    """Populate join tables from normalized entities + raw JSON."""
    create_db_and_tables(engine)
    class_features_created = 0
    subclass_features_created = 0
    spell_classes_created = 0
    missing_refs_count = 0

    with Session(engine) as session:
        source = _source_or_raise(session, source_name)
        import_run = ImportRun(
            status="started",
            source_id=source.id,
            source_name=source.name,
            run_key=f"relationships-{source.id}-{_utc_now().isoformat()}",
            started_at=_utc_now(),
        )
        session.add(import_run)
        session.commit()
        session.refresh(import_run)

        try:
            classes_by_key = {
                entry.source_key: entry
                for entry in session.exec(
                    select(DndClass).where(DndClass.source_id == source.id)
                ).all()
            }
            subclasses_by_key = {
                entry.source_key: entry
                for entry in session.exec(
                    select(Subclass).where(Subclass.source_id == source.id)
                ).all()
            }
            features_by_key = {
                entry.source_key: entry
                for entry in session.exec(
                    select(Feature).where(Feature.source_id == source.id)
                ).all()
            }
            spells_by_key = {
                entry.source_key: entry
                for entry in session.exec(
                    select(Spell).where(Spell.source_id == source.id)
                ).all()
            }

            existing_class_feature_keys = {
                (
                    link.source_id,
                    link.class_id,
                    link.feature_id,
                    _level_key(link.level),
                )
                for link in session.exec(
                    select(ClassFeatureLink).where(
                        ClassFeatureLink.source_id == source.id
                    )
                ).all()
            }
            existing_subclass_feature_keys = {
                (
                    link.source_id,
                    link.subclass_id,
                    link.feature_id,
                    _level_key(link.level),
                )
                for link in session.exec(
                    select(SubclassFeatureLink).where(
                        SubclassFeatureLink.source_id == source.id
                    )
                ).all()
            }
            existing_spell_class_keys = {
                (link.source_id, link.spell_id, link.class_id)
                for link in session.exec(
                    select(SpellClassLink).where(SpellClassLink.source_id == source.id)
                ).all()
            }

            new_class_features: list[ClassFeatureLink] = []
            new_subclass_features: list[SubclassFeatureLink] = []
            new_spell_classes: list[SpellClassLink] = []

            spell_entities = session.exec(
                select(RawEntity).where(
                    RawEntity.source_id == source.id,
                    RawEntity.entity_type == "spell",
                )
            ).all()
            for raw_entity in spell_entities:
                spell = spells_by_key.get(raw_entity.source_key)
                if spell is None:
                    missing_refs_count += 1
                    continue
                payload = raw_entity.raw_json or {}
                for class_index in _extract_class_indices(payload):
                    dnd_class = classes_by_key.get(class_index)
                    if dnd_class is None:
                        missing_refs_count += 1
                        continue
                    key = (source.id, spell.id, dnd_class.id)
                    if key in existing_spell_class_keys:
                        continue
                    existing_spell_class_keys.add(key)
                    new_spell_classes.append(
                        SpellClassLink(
                            source_id=source.id,
                            spell_id=spell.id,
                            class_id=dnd_class.id,
                        )
                    )

            feature_entities = session.exec(
                select(RawEntity).where(
                    RawEntity.source_id == source.id,
                    RawEntity.entity_type == "feature",
                )
            ).all()
            for raw_entity in feature_entities:
                feature = features_by_key.get(raw_entity.source_key)
                if feature is None:
                    missing_refs_count += 1
                    continue
                payload = raw_entity.raw_json or {}
                class_index, subclass_index, level = _extract_feature_refs(payload)
                if class_index:
                    dnd_class = classes_by_key.get(class_index)
                    if dnd_class is None:
                        missing_refs_count += 1
                    else:
                        key = (
                            source.id,
                            dnd_class.id,
                            feature.id,
                            _level_key(level),
                        )
                        if key not in existing_class_feature_keys:
                            existing_class_feature_keys.add(key)
                            new_class_features.append(
                                ClassFeatureLink(
                                    source_id=source.id,
                                    class_id=dnd_class.id,
                                    feature_id=feature.id,
                                    level=level,
                                )
                            )
                if subclass_index:
                    subclass = subclasses_by_key.get(subclass_index)
                    if subclass is None:
                        missing_refs_count += 1
                    else:
                        key = (
                            source.id,
                            subclass.id,
                            feature.id,
                            _level_key(level),
                        )
                        if key not in existing_subclass_feature_keys:
                            existing_subclass_feature_keys.add(key)
                            new_subclass_features.append(
                                SubclassFeatureLink(
                                    source_id=source.id,
                                    subclass_id=subclass.id,
                                    feature_id=feature.id,
                                    level=level,
                                )
                            )

            if new_spell_classes:
                session.add_all(new_spell_classes)
            if new_class_features:
                session.add_all(new_class_features)
            if new_subclass_features:
                session.add_all(new_subclass_features)
            session.commit()

            spell_classes_created = len(new_spell_classes)
            class_features_created = len(new_class_features)
            subclass_features_created = len(new_subclass_features)

            import_run.status = "success"
            import_run.finished_at = _utc_now()
            import_run.created_rows = (
                spell_classes_created
                + class_features_created
                + subclass_features_created
            )
            import_run.updated_rows = 0
            import_run.notes = json.dumps(
                {
                    "phase": "relationships",
                    "class_features_created": class_features_created,
                    "subclass_features_created": subclass_features_created,
                    "spell_classes_created": spell_classes_created,
                    "missing_refs_count": missing_refs_count,
                },
                sort_keys=True,
            )
            session.add(import_run)
            session.commit()
        except Exception as exc:
            import_run.status = "failed"
            import_run.finished_at = _utc_now()
            import_run.created_rows = (
                spell_classes_created
                + class_features_created
                + subclass_features_created
            )
            import_run.updated_rows = 0
            import_run.notes = json.dumps(
                {
                    "phase": "relationships",
                    "class_features_created": class_features_created,
                    "subclass_features_created": subclass_features_created,
                    "spell_classes_created": spell_classes_created,
                    "missing_refs_count": missing_refs_count,
                },
                sort_keys=True,
            )
            import_run.error = str(exc)
            session.add(import_run)
            session.commit()
            raise

    return {
        "class_features_created": class_features_created,
        "subclass_features_created": subclass_features_created,
        "spell_classes_created": spell_classes_created,
        "missing_refs_count": missing_refs_count,
    }
