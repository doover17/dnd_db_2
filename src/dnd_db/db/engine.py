"""Database engine helpers for dnd_db."""

from __future__ import annotations

from pathlib import Path

from sqlmodel import SQLModel, create_engine
from sqlalchemy.engine import Engine

from dnd_db.config import get_db_path


def get_engine(db_path: str | None = None) -> Engine:
    """Create a SQLite engine for the configured database path."""
    resolved_path = Path(db_path or get_db_path()).expanduser().resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{resolved_path}",
        connect_args={"check_same_thread": False},
    )


def create_db_and_tables(engine: Engine) -> None:
    """Create all database tables if they do not already exist."""
    from dnd_db import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
