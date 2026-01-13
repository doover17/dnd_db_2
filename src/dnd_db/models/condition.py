"""Normalized condition model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Index, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Condition(SQLModel, table=True):
    """Normalized condition data."""

    __tablename__ = "conditions"
    __table_args__ = (
        UniqueConstraint("source_id", "source_key", name="uq_conditions_source_key"),
        Index("ix_conditions_name", "name"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="sources.id", index=True)
    raw_entity_id: Optional[int] = Field(default=None, foreign_key="raw_entities.id")
    source_key: str = Field(sa_column=Column(String, nullable=False))
    name: str = Field(sa_column=Column(String, nullable=False))
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
