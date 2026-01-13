"""Choice loader pipeline."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlmodel import Session, select

from dnd_db.db.engine import create_db_and_tables
from dnd_db.models.choices import ChoiceGroup, ChoiceOption
from dnd_db.models.dnd_class import DndClass
from dnd_db.models.feature import Feature
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
        raise ValueError("Run importers first: source not found.")
    return source


def _is_choice_like(node: dict[str, Any]) -> bool:
    choose_key = any(key in node for key in ("choose", "choose_n", "count"))
    has_options = any(key in node for key in ("from", "options"))
    return choose_key and has_options


def _collect_choice_nodes(payload: Any) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if _is_choice_like(node):
                results.append(node)
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(payload)
    return results


def _extract_options(node: dict[str, Any]) -> list[Any]:
    options_value = node.get("options")
    from_value = node.get("from")

    if isinstance(from_value, dict):
        if "options" in from_value:
            options_value = from_value["options"]
        elif "from" in from_value:
            options_value = from_value["from"]
    elif isinstance(from_value, list) and options_value is None:
        options_value = from_value

    if isinstance(options_value, dict) and "options" in options_value:
        options_value = options_value["options"]

    if isinstance(options_value, list):
        return options_value
    return []


def _normalize_choice_type(value: Any) -> str:
    if not value:
        return "generic"
    candidate = str(value).strip().lower()
    if "fighting" in candidate and "style" in candidate:
        return "fighting_style"
    if "expertise" in candidate:
        return "expertise"
    if "invocation" in candidate:
        return "invocation"
    if "spell" in candidate:
        return "spell"
    if candidate in {"fighting_style", "expertise", "spell", "invocation"}:
        return candidate
    return "generic"


def _normalize_option_type(value: Any) -> str:
    if not value:
        return "generic"
    candidate = str(value).strip().lower()
    if candidate in {"feature", "class_feature", "subclass_feature"}:
        return "feature"
    if candidate in {"spell", "spellcasting"}:
        return "spell"
    if candidate in {"proficiency", "skill", "tool", "skill_proficiency"}:
        return "proficiency"
    return "generic"


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_label(option: dict[str, Any]) -> str | None:
    if "name" in option and isinstance(option["name"], str):
        return option["name"]
    if "string" in option and isinstance(option["string"], str):
        return option["string"]
    item = option.get("item")
    if isinstance(item, dict):
        item_name = item.get("name")
        if isinstance(item_name, str):
            return item_name
    return None


def _extract_source_key(option: dict[str, Any]) -> str | None:
    if "index" in option and isinstance(option["index"], str):
        return option["index"]
    item = option.get("item")
    if isinstance(item, dict):
        item_index = item.get("index")
        if isinstance(item_index, str):
            return item_index
    return None


def _extract_reference_type(option: dict[str, Any]) -> str | None:
    item = option.get("item")
    if isinstance(item, dict):
        item_type = item.get("type")
        if isinstance(item_type, str):
            return item_type
    return None


def _parse_option(option: Any, default_type: str) -> tuple[str, str, str]:
    if isinstance(option, str):
        label = option
        return default_type, _slugify(label), label
    if not isinstance(option, dict):
        return default_type, _slugify(str(option)), str(option)

    option_type = option.get("option_type") or option.get("type") or default_type
    ref_type = _extract_reference_type(option)
    if option_type == "reference":
        option_type = ref_type or default_type

    label = _extract_label(option)
    source_key = _extract_source_key(option)
    if not label and source_key:
        label = source_key
    if not source_key and label:
        source_key = _slugify(label)
    if not label:
        label = source_key or "unknown"
    if not source_key:
        source_key = _slugify(label)

    return str(option_type), source_key, label


def _choice_notes(choice_node: dict[str, Any]) -> str | None:
    for key in ("name", "desc", "notes"):
        value = choice_node.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            text = " ".join(entry for entry in value if isinstance(entry, str))
            if text:
                return text
    return None


def load_choices(*, engine, source_name: str = "5e-bits") -> dict[str, int]:
    """Populate choice groups and options from raw JSON."""
    create_db_and_tables(engine)
    group_created = 0
    option_created = 0
    missing_owner_count = 0
    missing_option_refs_count = 0

    with Session(engine) as session:
        source = _source_or_raise(session, source_name)
        import_run = ImportRun(
            status="started",
            source_id=source.id,
            source_name=source.name,
            phase="choices",
            run_key=f"choices-{source.id}-{_utc_now().isoformat()}",
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

            existing_groups = session.exec(
                select(ChoiceGroup).where(ChoiceGroup.source_id == source.id)
            ).all()
            group_lookup: dict[
                tuple[int, str, int, str, int, int, str | None], ChoiceGroup
            ] = {}
            for group in existing_groups:
                level_key = group.level if group.level is not None else -1
                group_lookup[
                    (
                        group.source_id,
                        group.owner_type,
                        group.owner_id,
                        group.choice_type,
                        group.choose_n,
                        level_key,
                        group.notes,
                    )
                ] = group

            existing_options = session.exec(
                select(ChoiceOption)
                .join(ChoiceGroup, ChoiceOption.choice_group_id == ChoiceGroup.id)
                .where(ChoiceGroup.source_id == source.id)
            ).all()
            option_keys = {
                (
                    option.choice_group_id,
                    option.option_type,
                    option.option_source_key,
                    option.label,
                )
                for option in existing_options
            }

            raw_entities = session.exec(
                select(RawEntity).where(
                    RawEntity.source_id == source.id,
                    RawEntity.entity_type.in_(["class", "subclass", "feature"]),
                )
            ).all()

            for raw_entity in raw_entities:
                payload = raw_entity.raw_json or {}
                owner_type = raw_entity.entity_type
                owner_id: int | None = None
                if owner_type == "class":
                    owner = classes_by_key.get(raw_entity.source_key)
                elif owner_type == "subclass":
                    owner = subclasses_by_key.get(raw_entity.source_key)
                else:
                    owner = features_by_key.get(raw_entity.source_key)
                if owner is None:
                    missing_owner_count += 1
                    continue
                owner_id = owner.id

                choices = _collect_choice_nodes(payload)
                for choice in choices:
                    choose_n = (
                        _coerce_int(choice.get("choose"))
                        or _coerce_int(choice.get("choose_n"))
                        or _coerce_int(choice.get("count"))
                    )
                    if choose_n is None:
                        continue
                    choice_type = _normalize_choice_type(choice.get("type"))
                    level = _coerce_int(choice.get("level")) or _coerce_int(
                        payload.get("level")
                    )
                    notes = _choice_notes(choice)
                    level_key = level if level is not None else -1
                    group_key = (
                        source.id,
                        owner_type,
                        owner_id,
                        choice_type,
                        choose_n,
                        level_key,
                        notes,
                    )
                    group = group_lookup.get(group_key)
                    if group is None:
                        group = ChoiceGroup(
                            source_id=source.id,
                            owner_type=owner_type,
                            owner_id=owner_id,
                            choice_type=choice_type,
                            choose_n=choose_n,
                            level=level,
                            notes=notes,
                        )
                        session.add(group)
                        session.flush()
                        group_created += 1
                        group_lookup[group_key] = group

                    options = _extract_options(choice)
                    for option in options:
                        option_type_raw, option_source_key, label = _parse_option(
                            option, choice_type
                        )
                        option_type = _normalize_option_type(option_type_raw)
                        option_key = (
                            group.id,
                            option_type,
                            option_source_key,
                            label,
                        )
                        if option_key in option_keys:
                            continue
                        option_ref_id = None
                        if option_type == "feature":
                            feature = features_by_key.get(option_source_key)
                            if feature is not None:
                                option_ref_id = feature.id
                            else:
                                missing_option_refs_count += 1
                        elif option_type == "spell":
                            spell = spells_by_key.get(option_source_key)
                            if spell is not None:
                                option_ref_id = spell.id
                            else:
                                missing_option_refs_count += 1
                        option_keys.add(option_key)
                        session.add(
                            ChoiceOption(
                                choice_group_id=group.id,
                                option_type=option_type,
                                option_source_key=option_source_key,
                                option_ref_id=option_ref_id,
                                label=label,
                            )
                        )
                        option_created += 1

            import_run.status = "finished"
            import_run.finished_at = _utc_now()
            import_run.created_rows = group_created + option_created
            import_run.notes = json.dumps(
                {
                    "choice_groups_created": group_created,
                    "choice_options_created": option_created,
                    "missing_owner_count": missing_owner_count,
                    "missing_option_refs_count": missing_option_refs_count,
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
        "choice_groups_created": group_created,
        "choice_options_created": option_created,
        "missing_owner_count": missing_owner_count,
        "missing_option_refs_count": missing_option_refs_count,
    }
