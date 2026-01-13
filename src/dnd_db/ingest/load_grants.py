"""Grant/effect loader pipeline."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlmodel import Session, select

from dnd_db.db.engine import create_db_and_tables
from dnd_db.models.dnd_class import DndClass
from dnd_db.models.feature import Feature
from dnd_db.models.grants import GrantFeature, GrantProficiency, GrantSpell
from dnd_db.models.import_run import ImportRun
from dnd_db.models.raw_entity import RawEntity
from dnd_db.models.source import Source
from dnd_db.models.spell import Spell
from dnd_db.models.subclass import Subclass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return slug.strip("-") or value.strip().lower()


def _source_or_raise(session: Session, source_name: str) -> Source:
    source = session.exec(select(Source).where(Source.name == source_name)).one_or_none()
    if source is None:
        raise ValueError("Source not found. Run importers first.")
    return source


def _extract_ref(item: Any) -> tuple[str, str]:
    if isinstance(item, dict):
        label = item.get("name")
        key = item.get("index") or item.get("source_key")
        if isinstance(label, str) and isinstance(key, str):
            return key, label
        if isinstance(label, str):
            return _slugify(label), label
        if isinstance(key, str):
            return key, key
    if isinstance(item, str):
        return _slugify(item), item
    label = str(item)
    return _slugify(label), label


def _extract_list(payload: dict[str, Any], keys: Iterable[str]) -> list[Any]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def _extract_nested_list(payload: dict[str, Any], parent_key: str, child_key: str) -> list[Any]:
    parent = payload.get(parent_key)
    if isinstance(parent, dict):
        value = parent.get(child_key)
        if isinstance(value, list):
            return value
    return []


def _collect_proficiency_grants(payload: dict[str, Any]) -> list[tuple[str, str, str]]:
    grants: list[tuple[str, str, str]] = []
    for key in (
        "proficiencies",
        "starting_proficiencies",
        "armor_proficiencies",
        "weapon_proficiencies",
        "tool_proficiencies",
        "skill_proficiencies",
    ):
        for item in _extract_list(payload, [key]):
            prof_key, label = _extract_ref(item)
            grants.append((key, prof_key, label))
    return grants


def _collect_spell_grants(payload: dict[str, Any]) -> list[tuple[str, str]]:
    grants: list[tuple[str, str]] = []
    for item in _extract_list(payload, ["spells"]):
        spell_key, label = _extract_ref(item)
        grants.append((spell_key, label))
    for item in _extract_nested_list(payload, "spellcasting", "spells"):
        spell_key, label = _extract_ref(item)
        grants.append((spell_key, label))
    return grants


def _collect_feature_grants(payload: dict[str, Any]) -> list[tuple[str, str]]:
    grants: list[tuple[str, str]] = []
    for item in _extract_list(payload, ["features", "granted_features"]):
        feature_key, label = _extract_ref(item)
        grants.append((feature_key, label))
    return grants


def load_grants(*, engine, source_name: str = "5e-bits") -> dict[str, int]:
    """Populate grant tables from raw JSON."""
    create_db_and_tables(engine)
    prof_created = 0
    spell_created = 0
    feature_created = 0
    missing_refs_count = 0

    with Session(engine) as session:
        source = _source_or_raise(session, source_name)
        import_run = ImportRun(
            status="started",
            source_id=source.id,
            source_name=source.name,
            phase="grants",
            run_key=f"grants-{source.id}-{_utc_now().isoformat()}",
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
            features_by_key = {
                entry.source_key: entry
                for entry in session.exec(
                    select(Feature).where(Feature.source_id == source.id)
                ).all()
            }
            subclasses_by_key = {
                entry.source_key: entry
                for entry in session.exec(
                    select(Subclass).where(Subclass.source_id == source.id)
                ).all()
            }
            spells_by_key = {
                entry.source_key: entry
                for entry in session.exec(
                    select(Spell).where(Spell.source_id == source.id)
                ).all()
            }

            existing_profs = session.exec(
                select(GrantProficiency).where(GrantProficiency.source_id == source.id)
            ).all()
            prof_keys = {
                (
                    entry.source_id,
                    entry.owner_type,
                    entry.owner_id,
                    entry.proficiency_type,
                    entry.proficiency_key,
                    entry.label,
                )
                for entry in existing_profs
            }

            existing_spells = session.exec(
                select(GrantSpell).where(GrantSpell.source_id == source.id)
            ).all()
            spell_keys = {
                (
                    entry.source_id,
                    entry.owner_type,
                    entry.owner_id,
                    entry.spell_source_key,
                    entry.label,
                )
                for entry in existing_spells
            }

            existing_features = session.exec(
                select(GrantFeature).where(GrantFeature.source_id == source.id)
            ).all()
            feature_keys = {
                (
                    entry.source_id,
                    entry.owner_type,
                    entry.owner_id,
                    entry.feature_source_key,
                    entry.label,
                )
                for entry in existing_features
            }

            raw_entities = session.exec(
                select(RawEntity).where(
                    RawEntity.source_id == source.id,
                    RawEntity.entity_type.in_(["class", "feature", "subclass"]),
                )
            ).all()

            for raw_entity in raw_entities:
                payload = raw_entity.raw_json or {}
                owner_type = raw_entity.entity_type
                if owner_type == "class":
                    owner = classes_by_key.get(raw_entity.source_key)
                elif owner_type == "subclass":
                    owner = subclasses_by_key.get(raw_entity.source_key)
                else:
                    owner = features_by_key.get(raw_entity.source_key)
                if owner is None:
                    continue
                owner_id = owner.id

                for prof_type, prof_key, label in _collect_proficiency_grants(payload):
                    prof_key_tuple = (
                        source.id,
                        owner_type,
                        owner_id,
                        prof_type,
                        prof_key,
                        label,
                    )
                    if prof_key_tuple in prof_keys:
                        continue
                    session.add(
                        GrantProficiency(
                            source_id=source.id,
                            owner_type=owner_type,
                            owner_id=owner_id,
                            proficiency_type=prof_type,
                            proficiency_key=prof_key,
                            label=label,
                        )
                    )
                    prof_keys.add(prof_key_tuple)
                    prof_created += 1

                for spell_key, label in _collect_spell_grants(payload):
                    spell_key_tuple = (
                        source.id,
                        owner_type,
                        owner_id,
                        spell_key,
                        label,
                    )
                    if spell_key_tuple in spell_keys:
                        continue
                    spell_id = None
                    spell = spells_by_key.get(spell_key)
                    if spell is not None:
                        spell_id = spell.id
                    else:
                        missing_refs_count += 1
                    session.add(
                        GrantSpell(
                            source_id=source.id,
                            owner_type=owner_type,
                            owner_id=owner_id,
                            spell_source_key=spell_key,
                            label=label,
                            spell_id=spell_id,
                        )
                    )
                    spell_keys.add(spell_key_tuple)
                    spell_created += 1

                for feature_key, label in _collect_feature_grants(payload):
                    feature_key_tuple = (
                        source.id,
                        owner_type,
                        owner_id,
                        feature_key,
                        label,
                    )
                    if feature_key_tuple in feature_keys:
                        continue
                    feature_id = None
                    feature = features_by_key.get(feature_key)
                    if feature is not None:
                        feature_id = feature.id
                    else:
                        missing_refs_count += 1
                    session.add(
                        GrantFeature(
                            source_id=source.id,
                            owner_type=owner_type,
                            owner_id=owner_id,
                            feature_source_key=feature_key,
                            label=label,
                            feature_id=feature_id,
                        )
                    )
                    feature_keys.add(feature_key_tuple)
                    feature_created += 1

            import_run.status = "success"
            import_run.finished_at = _utc_now()
            import_run.created_rows = prof_created + spell_created + feature_created
            import_run.notes = json.dumps(
                {
                    "grant_proficiencies_created": prof_created,
                    "grant_spells_created": spell_created,
                    "grant_features_created": feature_created,
                    "missing_refs_count": missing_refs_count,
                }
            )
        except Exception as exc:
            session.rollback()
            import_run.status = "failed"
            import_run.finished_at = _utc_now()
            import_run.error = str(exc)
            raise
        finally:
            session.add(import_run)
            session.commit()

    return {
        "grant_proficiencies_created": prof_created,
        "grant_spells_created": spell_created,
        "grant_features_created": feature_created,
        "missing_refs": missing_refs_count,
    }
