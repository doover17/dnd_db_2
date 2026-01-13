"""Normalized item/equipment model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Item(SQLModel, table=True):
    """Normalized equipment data."""

    __tablename__ = "items"
    __table_args__ = (
        UniqueConstraint("source_id", "source_key", name="uq_items_source_key"),
        Index("ix_items_name", "name"),
        Index("ix_items_equipment_category", "equipment_category"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="sources.id", index=True)
    raw_entity_id: Optional[int] = Field(default=None, foreign_key="raw_entities.id")
    source_key: str = Field(sa_column=Column(String, nullable=False))
    name: str = Field(sa_column=Column(String, nullable=False))

    equipment_category: Optional[str] = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    gear_category: Optional[str] = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    weapon_category: Optional[str] = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    armor_category: Optional[str] = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    tool_category: Optional[str] = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    vehicle_category: Optional[str] = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    category_range: Optional[str] = Field(
        default=None, sa_column=Column(String, nullable=True)
    )

    cost_quantity: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    cost_unit: Optional[str] = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    weight: Optional[float] = Field(
        default=None, sa_column=Column(Float, nullable=True)
    )

    desc: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    srd: Optional[bool] = Field(default=None, sa_column=Column(Boolean, nullable=True))
    api_url: Optional[str] = Field(default=None, sa_column=Column(String, nullable=True))

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            default=_utc_now,
            onupdate=_utc_now,
            nullable=False,
        )
    )
