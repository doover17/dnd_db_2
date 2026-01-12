"""Upsert helpers for raw entities."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from dnd_db.models.raw_entity import RawEntity


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def canonical_json_hash(payload: Any) -> str:
    """Return a sha256 hash of a canonical JSON serialization."""
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def upsert_raw_entity(
    session: Session,
    *,
    source_id: int,
    entity_type: str,
    source_key: str,
    payload: Any,
    name: str | None = None,
    srd: bool | None = None,
    url: str | None = None,
) -> tuple[RawEntity, bool, bool]:
    """Insert or update a raw entity, returning (entity, created, updated)."""
    raw_hash = canonical_json_hash(payload)
    statement = select(RawEntity).where(
        RawEntity.source_id == source_id,
        RawEntity.entity_type == entity_type,
        RawEntity.source_key == source_key,
    )
    existing = session.exec(statement).one_or_none()
    now = _utc_now()

    if existing is None:
        entity = RawEntity(
            source_id=source_id,
            entity_type=entity_type,
            source_key=source_key,
            name=name,
            srd=srd,
            url=url,
            raw_json=payload,
            raw_hash=raw_hash,
            retrieved_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(entity)
        session.commit()
        session.refresh(entity)
        return entity, True, False

    if existing.raw_hash == raw_hash:
        existing.retrieved_at = now
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing, False, False

    existing.raw_json = payload
    existing.raw_hash = raw_hash
    existing.name = name
    existing.srd = srd
    existing.url = url
    existing.retrieved_at = now
    existing.updated_at = now
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing, False, True
