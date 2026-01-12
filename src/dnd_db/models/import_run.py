"""Import run metadata model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ImportRun(SQLModel, table=True):
    """Track metadata for data import runs."""

    id: Optional[int] = Field(default=None, primary_key=True)
    started_at: datetime = Field(default_factory=_utc_now, index=True)
    finished_at: Optional[datetime] = Field(default=None, nullable=True)
    source_name: str
    source_version: Optional[str] = Field(default=None, nullable=True)
    notes: Optional[str] = Field(default=None, nullable=True)
    status: str = Field(index=True)
    created_rows: int = Field(default=0)
    updated_rows: int = Field(default=0)
    error: Optional[str] = Field(default=None, nullable=True)
