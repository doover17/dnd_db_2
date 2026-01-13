"""Import snapshot metadata model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime, Index, Integer, String, Text
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ImportSnapshot(SQLModel, table=True):
    """Stores summarized import metadata for diffing."""

    __tablename__ = "import_snapshots"
    __table_args__ = (
        Index("ix_import_snapshots_source", "source_id"),
        Index("ix_import_snapshots_run_key", "run_key"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="sources.id", index=True)
    run_key: Optional[str] = Field(default=None, sa_column=Column(String, nullable=True))
    counts_json: str = Field(sa_column=Column(Text, nullable=False))
    hashes_json: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    )
