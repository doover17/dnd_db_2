"""Choice and prerequisite models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ChoiceGroup(SQLModel, table=True):
    """Represents a choice point for a class, subclass, or feature."""

    __tablename__ = "choice_groups"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "owner_type",
            "owner_id",
            "choice_type",
            "choose_n",
            "level",
            "notes",
            name="uq_choice_groups_owner_choice",
        ),
        Index("ix_choice_groups_owner", "owner_type", "owner_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="sources.id", index=True)
    owner_type: str = Field(sa_column=Column(String, nullable=False))
    owner_id: int = Field(sa_column=Column(Integer, nullable=False))
    choice_type: str = Field(sa_column=Column(String, nullable=False))
    choose_n: int = Field(sa_column=Column(Integer, nullable=False))
    level: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    notes: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

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


class ChoiceOption(SQLModel, table=True):
    """Selectable option within a choice group."""

    __tablename__ = "choice_options"
    __table_args__ = (
        UniqueConstraint(
            "choice_group_id",
            "option_type",
            "option_source_key",
            "label",
            name="uq_choice_options_group_option",
        ),
        Index("ix_choice_options_group", "choice_group_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    choice_group_id: int = Field(foreign_key="choice_groups.id", index=True)
    option_type: str = Field(sa_column=Column(String, nullable=False))
    option_source_key: str = Field(sa_column=Column(String, nullable=False))
    option_ref_id: Optional[int] = Field(default=None, sa_column=Column(Integer))
    label: str = Field(sa_column=Column(String, nullable=False))

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


class Prerequisite(SQLModel, table=True):
    """Represents a prerequisite that gates features or choice groups."""

    __tablename__ = "prerequisites"
    __table_args__ = (
        Index("ix_prerequisites_applies_to", "applies_to_type", "applies_to_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    applies_to_type: str = Field(sa_column=Column(String, nullable=False))
    applies_to_id: int = Field(sa_column=Column(Integer, nullable=False))
    prereq_type: str = Field(sa_column=Column(String, nullable=False))
    key: str = Field(sa_column=Column(String, nullable=False))
    operator: str = Field(sa_column=Column(String, nullable=False))
    value: str = Field(sa_column=Column(String, nullable=False))
    notes: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

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
