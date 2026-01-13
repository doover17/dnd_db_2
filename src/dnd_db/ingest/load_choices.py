"""Choice loader pipeline."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from dnd_db.db.engine import create_db_and_tables
from dnd_db.models.choices import ChoiceGroup, ChoiceOption
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


def _is_choice_like(node: dict[str, Any]) -> bool:
    choose_key = any(key in node for key in ("choose", "choose_n", "count"))
    has_options = any(key in node for key in ("from", "options", "option_set"))
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
    option_set_value = node.get("option_set")

    if isinstance(from_value, dict):
        if "options" in from_value:
            options_value = from_value["options"]
        elif "from" in from_value:
            options_value = from_value["from"]
    elif isinstance(from_value, list) and options_value is None:
        options_value = from_value

    if isinstance(option_set_value, dict) and "options" in option_set_value:
        options_value = option_set_value["options"]

    if isinstance(options_value, dict) and "options" in options_value:
        options_value = options_value["options"]

    if isinstance(options_value, list):
        return options_value
    return []


def _normalize_option_type(value: Any) -> str:
    if not value:
        return "string"
    candidate = str(value).strip().lower()
    if candidate in {"feature", "class_feature", "subclass_feature"}:
        return "feature"
    if candidate in {"spell", "spells"}:
        return "spell"
    return "string"


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
    if "label" in option and isinstance(option["label"], str):
        return option["label"]
    item = option.get("item")
    if isinstance(item, dict):
        item_name = item.get("name")
        if isinstance(item_name, str):
            return item_name
    return None


def _extract_source_key(option: dict[str, Any]) -> str | None:
    if "index" in option and isinstance(option["index"], str):
        return option["index"]
    if "source_key" in option and isinstance(option["source_key"], str):
        return option["source_key"]
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
        item_url = item.get("url")
        if isinstance(item_url, str) and "/api/spells/" in item_url:
            return "spell"
    option_url = option.get("url")
    if isinstance(option_url, str) and "/api/spells/" in option_url:
        return "spell"
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


def _choice_label(choice_node: dict[str, Any]) -> str | None:
    for key in ("name", "label", "title"):
        value = choice_node.get(key)
        if isinstance(value, str):
            return value
    return None


def _infer_fighting_style(
    choice_node: dict[str, Any],
    options: list[Any],
    owner_name: str | None,
    owner_key: str | None,
) -> bool:
    type_value = str(choice_node.get("type") or "").lower()
    name_value = str(choice_node.get("name") or "").lower()
    if "fighting" in type_value and "style" in type_value:
        return True
    if "fighting" in name_value and "style" in name_value:
        return True
    owner_text = " ".join(
        token for token in [owner_name or "", owner_key or ""] if token
    ).lower()
    if "fighting style" in owner_text or "fighting-style" in owner_text:
        return True
    for option in options:
        if isinstance(option, dict):
            label = _extract_label(option)
            source_key = _extract_source_key(option)
        else:
            label = str(option)
            source_key = None
        option_text = " ".join(
            token
            for token in [label or "", source_key or ""]
            if isinstance(token, str)
        ).lower()
        if "fighting style" in option_text or "fighting-style" in option_text:
            return True
    return False


def _choice_text(choice_node: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("type", "name", "label", "title", "desc"):
        value = choice_node.get(key)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(entry for entry in value if isinstance(entry, str))
    return " ".join(parts).lower()


def _choice_keys_text(choice_node: dict[str, Any]) -> str:
    return " ".join(str(key) for key in choice_node.keys()).lower()


def _owner_text(owner_name: str | None, owner_key: str | None) -> str:
    return " ".join(token for token in [owner_name or "", owner_key or ""] if token).lower()


def _options_have_spell_reference(options: list[Any]) -> bool:
    for option in options:
        if isinstance(option, dict):
            option_type = option.get("option_type") or option.get("type")
            if isinstance(option_type, str) and "spell" in option_type.lower():
                return True
            ref_type = _extract_reference_type(option)
            if isinstance(ref_type, str) and ref_type.lower() == "spell":
                return True
            item = option.get("item")
            if isinstance(item, dict):
                item_url = item.get("url")
                if isinstance(item_url, str) and "/api/spells/" in item_url:
                    return True
        elif isinstance(option, str) and "spell" in option.lower():
            return True
    return False


def _infer_choice_type(
    choice_node: dict[str, Any],
    options: list[Any],
    owner_name: str | None,
    owner_key: str | None,
) -> str:
    if _infer_fighting_style(choice_node, options, owner_name, owner_key):
        return "fighting_style"

    choice_text = _choice_text(choice_node)
    key_text = _choice_keys_text(choice_node)
    owner_text = _owner_text(owner_name, owner_key)

    if "invocation" in choice_text or "invocation" in owner_text:
        return "invocation"
    if "expertise" in choice_text or "expertise" in owner_text:
        return "expertise"
    if (
        "spell" in choice_text
        or "cantrip" in choice_text
        or "spell" in key_text
        or "cantrip" in key_text
        or "spell" in owner_text
        or "cantrip" in owner_text
        or _options_have_spell_reference(options)
    ):
        return "spell"
    return "generic"


def _build_choice_source_key(
    *,
    owner_type: str,
    owner_key: str,
    choice_type: str,
    level: int | None,
    label: str | None,
) -> str:
    level_token = str(level) if level is not None else "na"
    label_token = _slugify(label) if label else "choice"
    return f"{owner_type}:{owner_key}:{choice_type}:{level_token}:{label_token}"


def load_choices(*, engine, source_name: str = "5e-bits") -> dict[str, int]:
    """Populate choice groups and options from raw JSON."""
    create_db_and_tables(engine)
    group_created = 0
    option_created = 0
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
            features_by_key = {
                entry.source_key: entry
                for entry in session.exec(
                    select(Feature).where(Feature.source_id == source.id)
                ).all()
            }

            existing_groups = session.exec(
                select(ChoiceGroup).where(ChoiceGroup.source_id == source.id)
            ).all()
            group_lookup: dict[
                tuple[int, str, int, str, int | None, str | None], ChoiceGroup
            ] = {}
            for group in existing_groups:
                group_lookup[
                    (
                        group.source_id,
                        group.owner_type,
                        group.owner_id,
                        group.choice_type,
                        group.level,
                        group.source_key,
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
                    RawEntity.entity_type.in_(["class", "feature"]),
                )
            ).all()

            for raw_entity in raw_entities:
                payload = raw_entity.raw_json or {}
                owner_type = raw_entity.entity_type
                owner_id: int | None = None
                if owner_type == "class":
                    owner = classes_by_key.get(raw_entity.source_key)
                else:
                    owner = features_by_key.get(raw_entity.source_key)
                if owner is None:
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
                    level = _coerce_int(choice.get("level")) or _coerce_int(
                        payload.get("level")
                    )
                    if level is None and getattr(owner, "level", None) is not None:
                        level = owner.level
                    notes = _choice_notes(choice)
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
                    source_key = _build_choice_source_key(
                        owner_type=owner_type,
                        owner_key=owner.source_key,
                        choice_type=choice_type,
                        level=level,
                        label=label,
                    )
                    group_key = (
                        source.id,
                        owner_type,
                        owner_id,
                        choice_type,
                        level,
                        source_key,
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
                            label=label,
                            notes=notes,
                            source_key=source_key,
                        )
                        session.add(group)
                        session.flush()
                        group_created += 1
                        group_lookup[group_key] = group

                    for option in options:
                        if choice_type in {"fighting_style", "invocation"}:
                            default_type = "feature"
                        elif choice_type == "spell":
                            default_type = "spell"
                        else:
                            default_type = "string"
                        option_type_raw, option_source_key, label = _parse_option(
                            option, default_type
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
                        feature_id = None
                        if option_type == "feature":
                            feature = features_by_key.get(option_source_key)
                            if feature is not None:
                                feature_id = feature.id
                            else:
                                missing_option_refs_count += 1
                        option_keys.add(option_key)
                        session.add(
                            ChoiceOption(
                                choice_group_id=group.id,
                                option_type=option_type,
                                option_source_key=option_source_key,
                                label=label,
                                feature_id=feature_id,
                            )
                        )
                        option_created += 1

            import_run.status = "success"
            import_run.finished_at = _utc_now()
            import_run.created_rows = group_created + option_created
            import_run.notes = json.dumps(
                {
                    "choice_groups_created": group_created,
                    "choice_options_created": option_created,
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
        "unresolved_feature_refs": missing_option_refs_count,
    }
