"""Normalized spell model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Spell(SQLModel, table=True):
    """Normalized spell data."""

    __tablename__ = "spells"
    __table_args__ = (
        UniqueConstraint("source_id", "source_key", name="uq_spells_source_key"),
        Index("ix_spells_name", "name"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="sources.id", index=True)
    raw_entity_id: Optional[int] = Field(default=None, foreign_key="raw_entities.id")
    source_key: str = Field(sa_column=Column(String, nullable=False))
    name: str = Field(sa_column=Column(String, nullable=False))

    level: int = Field(sa_column=Column(Integer, nullable=False))
    school: Optional[str] = Field(default=None, sa_column=Column(String, nullable=True))
    casting_time: Optional[str] = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    range: Optional[str] = Field(default=None, sa_column=Column(String, nullable=True))
    duration: Optional[str] = Field(default=None, sa_column=Column(String, nullable=True))
    concentration: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False)
    )
    ritual: bool = Field(default=False, sa_column=Column(Boolean, nullable=False))
    spell_desc: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    higher_level: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    components: Optional[str] = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    material: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    requires_attack_roll: Optional[bool] = Field(
        default=None, sa_column=Column(Boolean, nullable=True)
    )
    save_dc_ability: Optional[str] = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    damage_type: Optional[str] = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
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
