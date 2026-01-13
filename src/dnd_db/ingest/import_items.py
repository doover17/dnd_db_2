"""Item/equipment import pipeline."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from dnd_db.db.engine import create_db_and_tables
from dnd_db.db.upsert import upsert_raw_entity
from dnd_db.ingest.api_client import SrdApiClient
from dnd_db.models.import_run import ImportRun
from dnd_db.models.item import Item
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


def _join_paragraphs(values: Any) -> str | None:
    if not values:
        return None
    if isinstance(values, list):
        return "\n\n".join(str(entry) for entry in values if entry)
    if isinstance(values, str):
        return values
    return str(values)


def _ref_value(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if isinstance(value, dict):
        return value.get("name") or value.get("index")
    if isinstance(value, str):
        return value
    return None


def _cost_fields(payload: dict[str, Any]) -> tuple[int | None, str | None]:
    cost = payload.get("cost")
    if not isinstance(cost, dict):
        return None, None
    quantity = cost.get("quantity")
    unit = cost.get("unit")
    try:
        quantity_int = int(quantity) if quantity is not None else None
    except (TypeError, ValueError):
        quantity_int = None
    return quantity_int, unit if isinstance(unit, str) else None


def _weight_value(payload: dict[str, Any]) -> float | None:
    weight = payload.get("weight")
    if weight is None:
        return None
    try:
        return float(weight)
    except (TypeError, ValueError):
        return None


def _normalize_item_fields(payload: dict[str, Any]) -> dict[str, Any]:
    cost_quantity, cost_unit = _cost_fields(payload)
    return {
        "source_key": payload.get("index"),
        "name": payload.get("name"),
        "equipment_category": _ref_value(payload, "equipment_category"),
        "gear_category": _ref_value(payload, "gear_category"),
        "weapon_category": payload.get("weapon_category"),
        "armor_category": payload.get("armor_category"),
        "tool_category": payload.get("tool_category"),
        "vehicle_category": payload.get("vehicle_category"),
        "category_range": payload.get("category_range"),
        "cost_quantity": cost_quantity,
        "cost_unit": cost_unit,
        "weight": _weight_value(payload),
        "desc": _join_paragraphs(payload.get("desc")),
        "srd": payload.get("srd"),
        "api_url": payload.get("url"),
    }


def _upsert_item(
    session: Session,
    *,
    source_id: int,
    raw_entity: RawEntity,
    payload: dict[str, Any],
    raw_updated: bool,
) -> tuple[Item, bool, bool]:
    data = _normalize_item_fields(payload)
    statement = select(Item).where(
        Item.source_id == source_id,
        Item.source_key == data["source_key"],
    )
    existing = session.exec(statement).one_or_none()
    now = _utc_now()

    if existing is None:
        item = Item(
            source_id=source_id,
            raw_entity_id=raw_entity.id,
            source_key=data["source_key"],
            name=data["name"],
            equipment_category=data["equipment_category"],
            gear_category=data["gear_category"],
            weapon_category=data["weapon_category"],
            armor_category=data["armor_category"],
            tool_category=data["tool_category"],
            vehicle_category=data["vehicle_category"],
            category_range=data["category_range"],
            cost_quantity=data["cost_quantity"],
            cost_unit=data["cost_unit"],
            weight=data["weight"],
            desc=data["desc"],
            srd=data["srd"],
            api_url=data["api_url"],
            created_at=now,
            updated_at=now,
        )
        session.add(item)
        session.flush()
        return item, True, False

    needs_update = raw_updated or existing.raw_entity_id != raw_entity.id
    if not needs_update:
        return existing, False, False

    existing.raw_entity_id = raw_entity.id
    existing.name = data["name"]
    existing.equipment_category = data["equipment_category"]
    existing.gear_category = data["gear_category"]
    existing.weapon_category = data["weapon_category"]
    existing.armor_category = data["armor_category"]
    existing.tool_category = data["tool_category"]
    existing.vehicle_category = data["vehicle_category"]
    existing.category_range = data["category_range"]
    existing.cost_quantity = data["cost_quantity"]
    existing.cost_unit = data["cost_unit"]
    existing.weight = data["weight"]
    existing.desc = data["desc"]
    existing.srd = data["srd"]
    existing.api_url = data["api_url"]
    existing.updated_at = now
    session.add(existing)
    session.flush()
    return existing, False, True


def import_items(
    *,
    engine,
    base_url: str | None = None,
    limit: int | None = None,
    refresh: bool = False,
) -> int:
    """Imports items/equipment into raw_entities + items tables."""
    create_db_and_tables(engine)
    client = SrdApiClient(base_url=base_url, refresh=refresh)
    raw_created = 0
    raw_updated = 0
    item_created = 0
    item_updated = 0
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
            entries = client.list_resources("equipment")
            if limit is not None:
                entries = entries[:limit]

            for entry in entries:
                index = entry.get("index")
                url = entry.get("url")
                if not index or not url:
                    continue
                payload = client.get_by_url(url)
                processed += 1

                raw_entity, created, updated = upsert_raw_entity(
                    session,
                    source_id=source.id,
                    entity_type="equipment",
                    source_key=index,
                    payload=payload,
                    name=payload.get("name"),
                    srd=payload.get("srd"),
                    url=payload.get("url"),
                    commit=False,
                )
                raw_created += int(created)
                raw_updated += int(updated)

                _, item_was_created, item_was_updated = _upsert_item(
                    session,
                    source_id=source.id,
                    raw_entity=raw_entity,
                    payload=payload,
                    raw_updated=updated,
                )
                item_created += int(item_was_created)
                item_updated += int(item_was_updated)

            import_run.status = "success"
            import_run.finished_at = _utc_now()
            import_run.created_rows = raw_created + item_created
            import_run.notes = json.dumps(
                {
                    "raw_created": raw_created,
                    "raw_updated": raw_updated,
                    "item_created": item_created,
                    "item_updated": item_updated,
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

    return processed
