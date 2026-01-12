"""Raw entity payload storage model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, DateTime, Index, JSON, String, UniqueConstraint
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RawEntity(SQLModel, table=True):
    """Store raw JSON payloads from source APIs."""

    __tablename__ = "raw_entities"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "entity_type",
            "source_key",
            name="uq_raw_entities_source_type_key",
        ),
        Index("ix_raw_entities_entity_type_name", "entity_type", "name"),
        Index("ix_raw_entities_raw_hash", "raw_hash"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="sources.id", index=True)
    entity_type: str = Field(sa_column=Column(String, nullable=False))
    source_key: str = Field(sa_column=Column(String, nullable=False))
    name: Optional[str] = Field(default=None, nullable=True)
    srd: Optional[bool] = Field(default=None, nullable=True)
    url: Optional[str] = Field(default=None, nullable=True)
    raw_json: Any = Field(sa_column=Column(JSON, nullable=False))
    raw_hash: str = Field(sa_column=Column(String, nullable=False))
    retrieved_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    )
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
