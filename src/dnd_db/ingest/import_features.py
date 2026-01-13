"""Feature import pipeline."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from dnd_db.db.engine import create_db_and_tables
from dnd_db.db.upsert import upsert_raw_entity
from dnd_db.ingest.api_client import SrdApiClient
from dnd_db.models.feature import Feature
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


def _join_paragraphs(values: Any) -> str | None:
    if not values:
        return None
    if isinstance(values, list):
        return "\n\n".join(str(entry) for entry in values if entry)
    if isinstance(values, str):
        return values
    return str(values)


def _class_source_key(payload: dict[str, Any]) -> str | None:
    class_info = payload.get("class")
    if isinstance(class_info, dict):
        return class_info.get("index")
    return None


def _subclass_source_key(payload: dict[str, Any]) -> str | None:
    subclass_info = payload.get("subclass")
    if isinstance(subclass_info, dict):
        return subclass_info.get("index")
    return None


def _normalize_feature_fields(payload: dict[str, Any]) -> dict[str, Any]:
    level = payload.get("level")
    return {
        "source_key": payload.get("index"),
        "name": payload.get("name"),
        "level": int(level) if level is not None else None,
        "class_source_key": _class_source_key(payload),
        "subclass_source_key": _subclass_source_key(payload),
        "desc": _join_paragraphs(payload.get("desc")),
        "srd": payload.get("srd"),
        "api_url": payload.get("url"),
    }


def _upsert_feature(
    session: Session,
    *,
    source_id: int,
    raw_entity: RawEntity,
    payload: dict[str, Any],
    raw_updated: bool,
) -> tuple[Feature, bool, bool]:
    data = _normalize_feature_fields(payload)
    statement = select(Feature).where(
        Feature.source_id == source_id,
        Feature.source_key == data["source_key"],
    )
    existing = session.exec(statement).one_or_none()
    now = _utc_now()

    if existing is None:
        feature = Feature(
            source_id=source_id,
            raw_entity_id=raw_entity.id,
            source_key=data["source_key"],
            name=data["name"],
            level=data["level"],
            class_source_key=data["class_source_key"],
            subclass_source_key=data["subclass_source_key"],
            desc=data["desc"],
            srd=data["srd"],
            api_url=data["api_url"],
            created_at=now,
            updated_at=now,
        )
        session.add(feature)
        session.commit()
        session.refresh(feature)
        return feature, True, False

    needs_update = raw_updated or existing.raw_entity_id != raw_entity.id
    if not needs_update:
        return existing, False, False

    existing.raw_entity_id = raw_entity.id
    existing.name = data["name"]
    existing.level = data["level"]
    existing.class_source_key = data["class_source_key"]
    existing.subclass_source_key = data["subclass_source_key"]
    existing.desc = data["desc"]
    existing.srd = data["srd"]
    existing.api_url = data["api_url"]
    existing.updated_at = now
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing, False, True


def import_features(
    *,
    engine,
    base_url: str | None = None,
    limit: int | None = None,
    refresh: bool = False,
) -> int:
    """Imports features into raw_entities + features tables. Returns number processed."""
    create_db_and_tables(engine)
    client = SrdApiClient(base_url=base_url, refresh=refresh)
    raw_created = 0
    raw_updated = 0
    feature_created = 0
    feature_updated = 0
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
            entries = client.list_resources("features")
            if limit is not None:
                entries = entries[:limit]
            for entry in entries:
                index = entry.get("index")
                if not index:
                    continue
                if entry.get("url"):
                    payload = client.get_by_url(entry["url"])
                else:
                    payload = client.get_resource("features", index)
                raw_entity, created, updated = upsert_raw_entity(
                    session,
                    source_id=source.id,
                    entity_type="feature",
                    source_key=payload["index"],
                    payload=payload,
                    name=payload.get("name"),
                    srd=payload.get("srd"),
                    url=payload.get("url"),
                )
                raw_created += int(created)
                raw_updated += int(updated)
                _, feature_was_created, feature_was_updated = _upsert_feature(
                    session,
                    source_id=source.id,
                    raw_entity=raw_entity,
                    payload=payload,
                    raw_updated=updated,
                )
                feature_created += int(feature_was_created)
                feature_updated += int(feature_was_updated)
                processed += 1

            import_run.status = "success"
            import_run.finished_at = _utc_now()
            import_run.created_rows = raw_created + feature_created
            import_run.updated_rows = raw_updated + feature_updated
            import_run.notes = json.dumps(
                {
                    "raw_created": raw_created,
                    "raw_updated": raw_updated,
                    "feature_created": feature_created,
                    "feature_updated": feature_updated,
                },
                sort_keys=True,
            )
            session.add(import_run)
            session.commit()
        except Exception as exc:
            import_run.status = "failed"
            import_run.finished_at = _utc_now()
            import_run.created_rows = raw_created + feature_created
            import_run.updated_rows = raw_updated + feature_updated
            import_run.notes = json.dumps(
                {
                    "raw_created": raw_created,
                    "raw_updated": raw_updated,
                    "feature_created": feature_created,
                    "feature_updated": feature_updated,
                },
                sort_keys=True,
            )
            import_run.error = str(exc)
            session.add(import_run)
            session.commit()
            raise

    return processed
