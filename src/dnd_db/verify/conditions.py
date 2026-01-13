"""Verification checks for conditions."""

from __future__ import annotations

from sqlalchemy import func
from sqlmodel import Session, select

from dnd_db.models.condition import Condition
from dnd_db.models.raw_entity import RawEntity


def verify_conditions(session: Session) -> dict[str, list[str]]:
    """Verify condition integrity."""
    errors: list[str] = []
    warnings: list[str] = []

    duplicate_conditions = session.exec(
        select(
            Condition.source_id,
            Condition.source_key,
            func.count(Condition.id),
        )
        .group_by(Condition.source_id, Condition.source_key)
        .having(func.count(Condition.id) > 1)
    ).all()
    for source_id, source_key, count in duplicate_conditions:
        errors.append(
            "Duplicate condition: "
            f"source_id={source_id} source_key={source_key} count={count}"
        )

    missing_raw = session.exec(
        select(Condition)
        .outerjoin(RawEntity, RawEntity.id == Condition.raw_entity_id)
        .where(Condition.raw_entity_id.is_not(None), RawEntity.id.is_(None))
    ).all()
    for condition in missing_raw:
        errors.append(
            "Condition missing raw entity: "
            f"id={condition.id} raw_entity_id={condition.raw_entity_id}"
        )

    wrong_raw_type = session.exec(
        select(Condition)
        .join(RawEntity, RawEntity.id == Condition.raw_entity_id)
        .where(RawEntity.entity_type != "condition")
    ).all()
    for condition in wrong_raw_type:
        errors.append(
            "Condition raw entity type mismatch: "
            f"id={condition.id} raw_entity_id={condition.raw_entity_id}"
        )

    return {"errors": errors, "warnings": warnings}
