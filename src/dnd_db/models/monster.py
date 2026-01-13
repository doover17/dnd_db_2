"""Normalized monster model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Monster(SQLModel, table=True):
    """Normalized monster data."""

    __tablename__ = "monsters"
    __table_args__ = (
        UniqueConstraint("source_id", "source_key", name="uq_monsters_source_key"),
        Index("ix_monsters_name", "name"),
        Index("ix_monsters_type", "monster_type"),
        Index("ix_monsters_cr", "challenge_rating"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="sources.id", index=True)
    raw_entity_id: Optional[int] = Field(default=None, foreign_key="raw_entities.id")
    source_key: str = Field(sa_column=Column(String, nullable=False))
    name: str = Field(sa_column=Column(String, nullable=False))

    size: Optional[str] = Field(default=None, sa_column=Column(String, nullable=True))
    monster_type: Optional[str] = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    alignment: Optional[str] = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    challenge_rating: Optional[float] = Field(
        default=None, sa_column=Column(Float, nullable=True)
    )
    hit_points: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    armor_class: Optional[str] = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    speed: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
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
