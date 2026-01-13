"""Normalized subclass model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Index, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Subclass(SQLModel, table=True):
    """Normalized subclass data."""

    __tablename__ = "subclasses"
    __table_args__ = (
        UniqueConstraint("source_id", "source_key", name="uq_subclasses_source_key"),
        Index("ix_subclasses_name", "name"),
        Index("ix_subclasses_class_source_key", "class_source_key"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="sources.id", index=True)
    raw_entity_id: Optional[int] = Field(default=None, foreign_key="raw_entities.id")
    source_key: str = Field(sa_column=Column(String, nullable=False))
    name: str = Field(sa_column=Column(String, nullable=False))

    class_source_key: Optional[str] = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    subclass_flavor: Optional[str] = Field(
        default=None, sa_column=Column(String, nullable=True)
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
