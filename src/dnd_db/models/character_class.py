"""Normalized class model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CharacterClass(SQLModel, table=True):
    """Normalized class data."""

    __tablename__ = "classes"
    __table_args__ = (
        UniqueConstraint("source_id", "source_key", name="uq_classes_source_key"),
        Index("ix_classes_name", "name"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="sources.id", index=True)
    raw_entity_id: Optional[int] = Field(default=None, foreign_key="raw_entities.id")
    source_key: str = Field(sa_column=Column(String, nullable=False))
    name: str = Field(sa_column=Column(String, nullable=False))

    hit_die: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    proficiencies: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    saving_throws: Optional[str] = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    spellcasting_ability: Optional[str] = Field(
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
