"""Class import pipeline."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from dnd_db.db.engine import create_db_and_tables
from dnd_db.db.upsert import upsert_raw_entity
from dnd_db.ingest.api_client import SrdApiClient
from dnd_db.models.dnd_class import DndClass
from dnd_db.models.import_run import ImportRun
from dnd_db.models.raw_entity import RawEntity
from dnd_db.models.source import Source


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_source(session: Session, name: str, base_url: str | None) -> Source:
    existing = session.exec(select(Source).where(Source.name == name)).one_or_none()
    if existing is not None:
        if base_url and existing.base_url != base_url:
            existing.base_url = base_url
            session.add(existing)
            session.commit()
            session.refresh(existing)
        return existing
    source = Source(name=name, base_url=base_url)
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


def _list_values(values: Any) -> list[str] | None:
    if not values:
        return None
    if isinstance(values, list):
        names: list[str] = []
        for entry in values:
            if isinstance(entry, dict):
                label = entry.get("name") or entry.get("index")
                if label:
                    names.append(str(label))
            elif isinstance(entry, str):
                names.append(entry)
        return names if names else None
    if isinstance(values, str):
        return [values]
    return None


def _json_list(values: Any) -> str | None:
    items = _list_values(values)
    if not items:
        return None
    return json.dumps(items, sort_keys=True)


def _spellcasting_ability(payload: dict[str, Any]) -> str | None:
    spellcasting = payload.get("spellcasting")
    if isinstance(spellcasting, dict):
        ability = spellcasting.get("spellcasting_ability")
        if isinstance(ability, dict):
            return ability.get("name") or ability.get("index")
    return None


def _starting_equipment(payload: dict[str, Any]) -> str | None:
    equipment = payload.get("starting_equipment")
    if not isinstance(equipment, list):
        return None
    items: list[Any] = []
    for entry in equipment:
        if isinstance(entry, dict):
            item: dict[str, Any] = {}
            quantity = entry.get("quantity")
            if quantity is not None:
                item["quantity"] = quantity
            equip = entry.get("equipment")
            if isinstance(equip, dict):
                name = equip.get("name") or equip.get("index")
                if name:
                    item["equipment"] = name
            elif isinstance(equip, str):
                item["equipment"] = equip
            if item:
                items.append(item)
        elif isinstance(entry, str):
            items.append(entry)
    if not items:
        return None
    return json.dumps(items, sort_keys=True)


def _normalize_class_fields(payload: dict[str, Any]) -> dict[str, Any]:
    hit_die = payload.get("hit_die")
    return {
        "source_key": payload.get("index"),
        "name": payload.get("name"),
        "hit_die": int(hit_die) if hit_die is not None else None,
        "proficiencies": _json_list(payload.get("proficiencies")),
        "saves": _json_list(payload.get("saving_throws")),
        "spellcasting_ability": _spellcasting_ability(payload),
        "starting_equipment": _starting_equipment(payload),
        "srd": payload.get("srd"),
        "api_url": payload.get("url"),
    }


def _upsert_class(
    session: Session,
    *,
    source_id: int,
    raw_entity: RawEntity,
    payload: dict[str, Any],
    raw_updated: bool,
) -> tuple[DndClass, bool, bool]:
    data = _normalize_class_fields(payload)
    statement = select(DndClass).where(
        DndClass.source_id == source_id,
        DndClass.source_key == data["source_key"],
    )
    existing = session.exec(statement).one_or_none()
    now = _utc_now()

    if existing is None:
        character_class = DndClass(
            source_id=source_id,
            raw_entity_id=raw_entity.id,
            source_key=data["source_key"],
            name=data["name"],
            hit_die=data["hit_die"],
            spellcasting_ability=data["spellcasting_ability"],
            saves=data["saves"],
            proficiencies=data["proficiencies"],
            starting_equipment=data["starting_equipment"],
            srd=data["srd"],
            api_url=data["api_url"],
            created_at=now,
            updated_at=now,
        )
        session.add(character_class)
        session.commit()
        session.refresh(character_class)
        return character_class, True, False

    needs_update = raw_updated or existing.raw_entity_id != raw_entity.id
    if not needs_update:
        return existing, False, False

    existing.raw_entity_id = raw_entity.id
    existing.name = data["name"]
    existing.hit_die = data["hit_die"]
    existing.spellcasting_ability = data["spellcasting_ability"]
    existing.saves = data["saves"]
    existing.proficiencies = data["proficiencies"]
    existing.starting_equipment = data["starting_equipment"]
    existing.srd = data["srd"]
    existing.api_url = data["api_url"]
    existing.updated_at = now
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing, False, True


def import_classes(
    *,
    engine,
    base_url: str | None = None,
    limit: int | None = None,
    refresh: bool = False,
) -> int:
    """Imports classes into raw_entities + classes tables. Returns number processed."""
    create_db_and_tables(engine)
    client = SrdApiClient(base_url=base_url, refresh=refresh)
    raw_created = 0
    raw_updated = 0
    class_created = 0
    class_updated = 0
    processed = 0

    with Session(engine) as session:
        source = _ensure_source(session, "5e-bits", client.base_url)
        import_run = ImportRun(
            status="started",
            source_id=source.id,
            source_name=source.name,
            started_at=_utc_now(),
        )
        session.add(import_run)
        session.commit()
        session.refresh(import_run)

        try:
            entries = client.list_resources("classes")
            if limit is not None:
                entries = entries[:limit]
            for entry in entries:
                index = entry.get("index")
                if not index:
                    continue
                if entry.get("url"):
                    payload = client.get_by_url(entry["url"])
                else:
                    payload = client.get_resource("classes", index)
                raw_entity, created, updated = upsert_raw_entity(
                    session,
                    source_id=source.id,
                    entity_type="class",
                    source_key=payload["index"],
                    payload=payload,
                    name=payload.get("name"),
                    srd=payload.get("srd"),
                    url=payload.get("url"),
                )
                raw_created += int(created)
                raw_updated += int(updated)
                _, class_was_created, class_was_updated = _upsert_class(
                    session,
                    source_id=source.id,
                    raw_entity=raw_entity,
                    payload=payload,
                    raw_updated=updated,
                )
                class_created += int(class_was_created)
                class_updated += int(class_was_updated)
                processed += 1

            import_run.status = "success"
            import_run.finished_at = _utc_now()
            import_run.created_rows = raw_created + class_created
            import_run.updated_rows = raw_updated + class_updated
            import_run.notes = json.dumps(
                {
                    "raw_created": raw_created,
                    "raw_updated": raw_updated,
                    "class_created": class_created,
                    "class_updated": class_updated,
                },
                sort_keys=True,
            )
            session.add(import_run)
            session.commit()
        except Exception as exc:
            import_run.status = "failed"
            import_run.finished_at = _utc_now()
            import_run.created_rows = raw_created + class_created
            import_run.updated_rows = raw_updated + class_updated
            import_run.notes = json.dumps(
                {
                    "raw_created": raw_created,
                    "raw_updated": raw_updated,
                    "class_created": class_created,
                    "class_updated": class_updated,
                },
                sort_keys=True,
            )
            import_run.error = str(exc)
            session.add(import_run)
            session.commit()
            raise

    return processed
