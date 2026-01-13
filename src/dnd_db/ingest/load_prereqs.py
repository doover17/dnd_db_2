"""Prerequisite loader pipeline."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlmodel import Session, select

from dnd_db.db.engine import create_db_and_tables
from dnd_db.ingest.load_choices import (
    _build_choice_source_key,
    _choice_label,
    _coerce_int,
    _collect_choice_nodes,
    _extract_options,
    _infer_choice_type,
)
from dnd_db.models.choices import ChoiceGroup, Prerequisite
from dnd_db.models.dnd_class import DndClass
from dnd_db.models.feature import Feature
from dnd_db.models.import_run import ImportRun
from dnd_db.models.raw_entity import RawEntity
from dnd_db.models.source import Source


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


def _extract_key(value: Any) -> str | None:
    if isinstance(value, dict):
        if isinstance(value.get("index"), str):
            return value["index"]
        if isinstance(value.get("name"), str):
            return _slugify(value["name"])
    if isinstance(value, str):
        return _slugify(value)
    return None


def _extract_prereq_nodes(node: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("prerequisites", "prerequisite", "requirements", "requirement"):
        value = node.get(key)
        if isinstance(value, list):
            return [entry for entry in value if isinstance(entry, dict)]
        if isinstance(value, dict):
            return [value]
    return []


def _entry_notes(entry: dict[str, Any]) -> str | None:
    for key in ("name", "desc", "note"):
        value = entry.get(key)
        if isinstance(value, str):
            return value
    return None


def _parse_prereq_entry(entry: dict[str, Any]) -> list[tuple[str, str, str, str, str | None]]:
    results: list[tuple[str, str, str, str, str | None]] = []
    entry_type = str(entry.get("type") or "").lower()
    operator = str(entry.get("operator") or "").strip() or None
    notes = _entry_notes(entry)

    level_value = _coerce_int(entry.get("level"))
    if level_value is None:
        level_value = _coerce_int(entry.get("minimum_level"))
    has_level = level_value is not None
    if has_level:
        class_key = _extract_key(entry.get("class"))
        results.append(
            (
                "level",
                class_key or "any",
                operator or ">=",
                str(level_value),
                notes,
            )
        )

    class_key = _extract_key(entry.get("class"))
    if class_key and (
        entry_type == "class" or ("class" in entry and not has_level and entry_type != "level")
    ):
        results.append(("class", class_key, operator or "==", "true", notes))

    subclass_key = _extract_key(entry.get("subclass"))
    if subclass_key and (entry_type == "subclass" or "subclass" in entry):
        results.append(("subclass", subclass_key, operator or "==", "true", notes))

    ability_value = entry.get("ability_score") or entry.get("ability")
    ability_key = _extract_key(ability_value) or _extract_key(entry.get("ability_score"))
    min_score = _coerce_int(entry.get("minimum_score"))
    if min_score is None:
        min_score = _coerce_int(entry.get("score"))
    if min_score is None:
        min_score = _coerce_int(entry.get("value"))
    if ability_key and min_score is not None:
        results.append(
            ("ability", ability_key, operator or ">=", str(min_score), notes)
        )

    feature_key = _extract_key(entry.get("feature")) or _extract_key(
        entry.get("prerequisite_feature")
    )
    if feature_key and (entry_type == "feature" or "feature" in entry):
        results.append(("feature", feature_key, operator or "==", "true", notes))

    return results


def _iter_prereqs(nodes: Iterable[dict[str, Any]]) -> list[tuple[str, str, str, str, str | None]]:
    results: list[tuple[str, str, str, str, str | None]] = []
    for entry in nodes:
        results.extend(_parse_prereq_entry(entry))
    return results


def load_prereqs(*, engine, source_name: str = "5e-bits") -> dict[str, int]:
    """Populate prerequisites from raw JSON."""
    create_db_and_tables(engine)
    created = 0
    missing_refs_count = 0

    with Session(engine) as session:
        source = _source_or_raise(session, source_name)
        import_run = ImportRun(
            status="started",
            source_id=source.id,
            source_name=source.name,
            phase="prereqs",
            run_key=f"prereqs-{source.id}-{_utc_now().isoformat()}",
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
            choice_groups_by_source_key = {
                group.source_key: group
                for group in session.exec(
                    select(ChoiceGroup).where(ChoiceGroup.source_id == source.id)
                ).all()
                if group.source_key
            }

            existing_prereqs = session.exec(select(Prerequisite)).all()
            prereq_keys = {
                (
                    prereq.applies_to_type,
                    prereq.applies_to_id,
                    prereq.prereq_type,
                    prereq.key,
                    prereq.operator,
                    prereq.value,
                )
                for prereq in existing_prereqs
            }

            raw_entities = session.exec(
                select(RawEntity).where(
                    RawEntity.source_id == source.id,
                    RawEntity.entity_type.in_(["class", "feature"]),
                )
            ).all()

            for raw_entity in raw_entities:
                payload = raw_entity.raw_json or {}
                owner_type = raw_entity.entity_type
                if owner_type == "class":
                    owner = classes_by_key.get(raw_entity.source_key)
                else:
                    owner = features_by_key.get(raw_entity.source_key)
                if owner is None:
                    continue

                prereq_nodes = _extract_prereq_nodes(payload)
                if prereq_nodes and owner_type == "feature":
                    prereqs = _iter_prereqs(prereq_nodes)
                    for prereq_type, key, operator, value, notes in prereqs:
                        prereq_key = (
                            "feature",
                            owner.id,
                            prereq_type,
                            key,
                            operator,
                            value,
                        )
                        if prereq_key in prereq_keys:
                            continue
                        session.add(
                            Prerequisite(
                                applies_to_type="feature",
                                applies_to_id=owner.id,
                                prereq_type=prereq_type,
                                key=key,
                                operator=operator,
                                value=value,
                                notes=notes,
                            )
                        )
                        prereq_keys.add(prereq_key)
                        created += 1

                choice_nodes = _collect_choice_nodes(payload)
                for choice in choice_nodes:
                    choice_prereqs = _extract_prereq_nodes(choice)
                    if not choice_prereqs:
                        continue

                    level = _coerce_int(choice.get("level")) or _coerce_int(
                        payload.get("level")
                    )
                    if level is None and getattr(owner, "level", None) is not None:
                        level = owner.level
                    label = _choice_label(choice)
                    options = _extract_options(choice)
                    choice_type = _infer_choice_type(
                        choice, options, getattr(owner, "name", None), owner.source_key
                    )
                    if choice_type == "fighting_style" and not label:
                        label = "Fighting Style"
                    if choice_type == "expertise" and not label:
                        label = "Expertise"
                    if choice_type == "invocation" and not label:
                        label = "Invocations"
                    if choice_type == "spell" and not label:
                        label = "Spell Choice"

                    choice_source_key = _build_choice_source_key(
                        owner_type=owner_type,
                        owner_key=owner.source_key,
                        choice_type=choice_type,
                        level=level,
                        label=label,
                    )
                    choice_group = choice_groups_by_source_key.get(choice_source_key)
                    if choice_group is None:
                        missing_refs_count += 1
                        continue

                    prereqs = _iter_prereqs(choice_prereqs)
                    for prereq_type, key, operator, value, notes in prereqs:
                        prereq_key = (
                            "choice_group",
                            choice_group.id,
                            prereq_type,
                            key,
                            operator,
                            value,
                        )
                        if prereq_key in prereq_keys:
                            continue
                        session.add(
                            Prerequisite(
                                applies_to_type="choice_group",
                                applies_to_id=choice_group.id,
                                prereq_type=prereq_type,
                                key=key,
                                operator=operator,
                                value=value,
                                notes=notes,
                            )
                        )
                        prereq_keys.add(prereq_key)
                        created += 1

            import_run.status = "success"
            import_run.finished_at = _utc_now()
            import_run.created_rows = created
            import_run.notes = json.dumps(
                {"prereqs_created": created, "missing_refs_count": missing_refs_count}
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

    return {"prereqs_created": created, "missing_refs": missing_refs_count}
