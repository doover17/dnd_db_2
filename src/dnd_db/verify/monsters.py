"""Verification checks for monsters."""

from __future__ import annotations

from sqlalchemy import func
from sqlmodel import Session, select

from dnd_db.models.monster import Monster
from dnd_db.models.raw_entity import RawEntity


def verify_monsters(session: Session) -> dict[str, list[str]]:
    """Verify monster integrity."""
    errors: list[str] = []
    warnings: list[str] = []

    duplicate_monsters = session.exec(
        select(
            Monster.source_id,
            Monster.source_key,
            func.count(Monster.id),
        )
        .group_by(Monster.source_id, Monster.source_key)
        .having(func.count(Monster.id) > 1)
    ).all()
    for source_id, source_key, count in duplicate_monsters:
        errors.append(
            "Duplicate monster: "
            f"source_id={source_id} source_key={source_key} count={count}"
        )

    missing_raw = session.exec(
        select(Monster)
        .outerjoin(RawEntity, RawEntity.id == Monster.raw_entity_id)
        .where(Monster.raw_entity_id.is_not(None), RawEntity.id.is_(None))
    ).all()
    for monster in missing_raw:
        errors.append(
            "Monster missing raw entity: "
            f"id={monster.id} raw_entity_id={monster.raw_entity_id}"
        )

    wrong_raw_type = session.exec(
        select(Monster)
        .join(RawEntity, RawEntity.id == Monster.raw_entity_id)
        .where(RawEntity.entity_type != "monster")
    ).all()
    for monster in wrong_raw_type:
        errors.append(
            "Monster raw entity type mismatch: "
            f"id={monster.id} raw_entity_id={monster.raw_entity_id}"
        )

    return {"errors": errors, "warnings": warnings}
