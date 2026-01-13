"""Verification checks for items."""

from __future__ import annotations

from sqlalchemy import func
from sqlmodel import Session, select

from dnd_db.models.item import Item
from dnd_db.models.raw_entity import RawEntity


def verify_items(session: Session) -> dict[str, list[str]]:
    """Verify item integrity."""
    errors: list[str] = []
    warnings: list[str] = []

    duplicate_items = session.exec(
        select(
            Item.source_id,
            Item.source_key,
            func.count(Item.id),
        )
        .group_by(Item.source_id, Item.source_key)
        .having(func.count(Item.id) > 1)
    ).all()
    for source_id, source_key, count in duplicate_items:
        errors.append(
            "Duplicate item: "
            f"source_id={source_id} source_key={source_key} count={count}"
        )

    missing_raw = session.exec(
        select(Item)
        .outerjoin(RawEntity, RawEntity.id == Item.raw_entity_id)
        .where(Item.raw_entity_id.is_not(None), RawEntity.id.is_(None))
    ).all()
    for item in missing_raw:
        errors.append(
            "Item missing raw entity: "
            f"id={item.id} raw_entity_id={item.raw_entity_id}"
        )

    wrong_raw_type = session.exec(
        select(Item)
        .join(RawEntity, RawEntity.id == Item.raw_entity_id)
        .where(RawEntity.entity_type != "equipment")
    ).all()
    for item in wrong_raw_type:
        errors.append(
            "Item raw entity type mismatch: "
            f"id={item.id} raw_entity_id={item.raw_entity_id}"
        )

    return {"errors": errors, "warnings": warnings}
