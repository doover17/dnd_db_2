"""Spell import pipeline."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from dnd_db.db.engine import create_db_and_tables
from dnd_db.db.upsert import upsert_raw_entity
from dnd_db.ingest.api_client import SrdApiClient
from dnd_db.models.import_run import ImportRun
from dnd_db.models.raw_entity import RawEntity
from dnd_db.models.source import Source
from dnd_db.models.spell import Spell


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


def _school_value(payload: dict[str, Any]) -> str | None:
    school = payload.get("school")
    if isinstance(school, dict):
        return school.get("name") or school.get("index")
    return None


def _dc_ability(payload: dict[str, Any]) -> str | None:
    dc = payload.get("dc")
    if not isinstance(dc, dict):
        return None
    dc_type = dc.get("dc_type")
    if isinstance(dc_type, dict):
        return dc_type.get("name") or dc_type.get("index")
    return None


def _damage_type(payload: dict[str, Any]) -> str | None:
    damage = payload.get("damage")
    if not isinstance(damage, dict):
        return None
    damage_type = damage.get("damage_type")
    if isinstance(damage_type, dict):
        return damage_type.get("name") or damage_type.get("index")
    return None


def _components_value(payload: dict[str, Any]) -> str | None:
    components = payload.get("components")
    if not components:
        return None
    if isinstance(components, list):
        return ",".join(components)
    if isinstance(components, str):
        return components
    return None


def _requires_attack_roll(payload: dict[str, Any]) -> bool | None:
    if "attack_type" not in payload:
        return None
    return bool(payload.get("attack_type"))


def _normalize_spell_fields(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_key": payload.get("index"),
        "name": payload.get("name"),
        "level": int(payload.get("level") or 0),
        "school": _school_value(payload),
        "casting_time": payload.get("casting_time"),
        "range": payload.get("range"),
        "duration": payload.get("duration"),
        "concentration": bool(payload.get("concentration") or False),
        "ritual": bool(payload.get("ritual") or False),
        "spell_desc": _join_paragraphs(payload.get("desc")),
        "higher_level": _join_paragraphs(payload.get("higher_level")),
        "components": _components_value(payload),
        "material": payload.get("material"),
        "requires_attack_roll": _requires_attack_roll(payload),
        "save_dc_ability": _dc_ability(payload),
        "damage_type": _damage_type(payload),
        "srd": payload.get("srd"),
        "api_url": payload.get("url"),
    }


def _upsert_spell(
    session: Session,
    *,
    source_id: int,
    raw_entity: RawEntity,
    payload: dict[str, Any],
    raw_updated: bool,
) -> tuple[Spell, bool, bool]:
    data = _normalize_spell_fields(payload)
    statement = select(Spell).where(
        Spell.source_id == source_id,
        Spell.source_key == data["source_key"],
    )
    existing = session.exec(statement).one_or_none()
    now = _utc_now()

    if existing is None:
        spell = Spell(
            source_id=source_id,
            raw_entity_id=raw_entity.id,
            source_key=data["source_key"],
            name=data["name"],
            level=data["level"],
            school=data["school"],
            casting_time=data["casting_time"],
            range=data["range"],
            duration=data["duration"],
            concentration=data["concentration"],
            ritual=data["ritual"],
            spell_desc=data["spell_desc"],
            higher_level=data["higher_level"],
            components=data["components"],
            material=data["material"],
            requires_attack_roll=data["requires_attack_roll"],
            save_dc_ability=data["save_dc_ability"],
            damage_type=data["damage_type"],
            srd=data["srd"],
            api_url=data["api_url"],
            created_at=now,
            updated_at=now,
        )
        session.add(spell)
        session.commit()
        session.refresh(spell)
        return spell, True, False

    needs_update = raw_updated or existing.raw_entity_id != raw_entity.id
    if not needs_update:
        return existing, False, False

    existing.raw_entity_id = raw_entity.id
    existing.name = data["name"]
    existing.level = data["level"]
    existing.school = data["school"]
    existing.casting_time = data["casting_time"]
    existing.range = data["range"]
    existing.duration = data["duration"]
    existing.concentration = data["concentration"]
    existing.ritual = data["ritual"]
    existing.spell_desc = data["spell_desc"]
    existing.higher_level = data["higher_level"]
    existing.components = data["components"]
    existing.material = data["material"]
    existing.requires_attack_roll = data["requires_attack_roll"]
    existing.save_dc_ability = data["save_dc_ability"]
    existing.damage_type = data["damage_type"]
    existing.srd = data["srd"]
    existing.api_url = data["api_url"]
    existing.updated_at = now
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing, False, True


def import_spells(
    *,
    engine,
    base_url: str | None = None,
    limit: int | None = None,
    refresh: bool = False,
) -> int:
    """Imports spells into raw_entities + spells tables. Returns number of spells processed."""
    create_db_and_tables(engine)
    client = SrdApiClient(base_url=base_url, refresh=refresh)
    raw_created = 0
    raw_updated = 0
    spell_created = 0
    spell_updated = 0
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
            entries = client.list_resources("spells")
            if limit is not None:
                entries = entries[:limit]
            for entry in entries:
                index = entry.get("index")
                if not index:
                    continue
                if entry.get("url"):
                    payload = client.get_by_url(entry["url"])
                else:
                    payload = client.get_resource("spells", index)
                raw_entity, created, updated = upsert_raw_entity(
                    session,
                    source_id=source.id,
                    entity_type="spell",
                    source_key=payload["index"],
                    payload=payload,
                    name=payload.get("name"),
                    srd=payload.get("srd"),
                    url=payload.get("url"),
                )
                raw_created += int(created)
                raw_updated += int(updated)
                _, spell_was_created, spell_was_updated = _upsert_spell(
                    session,
                    source_id=source.id,
                    raw_entity=raw_entity,
                    payload=payload,
                    raw_updated=updated,
                )
                spell_created += int(spell_was_created)
                spell_updated += int(spell_was_updated)
                processed += 1

            import_run.status = "success"
            import_run.finished_at = _utc_now()
            import_run.created_rows = raw_created + spell_created
            import_run.updated_rows = raw_updated + spell_updated
            import_run.notes = json.dumps(
                {
                    "raw_created": raw_created,
                    "raw_updated": raw_updated,
                    "spell_created": spell_created,
                    "spell_updated": spell_updated,
                },
                sort_keys=True,
            )
            session.add(import_run)
            session.commit()
        except Exception as exc:
            import_run.status = "failed"
            import_run.finished_at = _utc_now()
            import_run.created_rows = raw_created + spell_created
            import_run.updated_rows = raw_updated + spell_updated
            import_run.notes = json.dumps(
                {
                    "raw_created": raw_created,
                    "raw_updated": raw_updated,
                    "spell_created": spell_created,
                    "spell_updated": spell_updated,
                },
                sort_keys=True,
            )
            import_run.error = str(exc)
            session.add(import_run)
            session.commit()
            raise

    return processed
