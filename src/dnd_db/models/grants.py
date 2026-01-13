"""Grant/effect models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime, Index, Integer, String, UniqueConstraint
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GrantProficiency(SQLModel, table=True):
    """Declared proficiency grant."""

    __tablename__ = "grant_proficiencies"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "owner_type",
            "owner_id",
            "proficiency_type",
            "proficiency_key",
            "label",
            name="uq_grant_proficiencies_owner",
        ),
        Index("ix_grant_proficiencies_owner", "owner_type", "owner_id"),
        Index("ix_grant_proficiencies_type", "proficiency_type"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="sources.id", index=True)
    owner_type: str = Field(sa_column=Column(String, nullable=False))
    owner_id: int = Field(sa_column=Column(Integer, nullable=False))
    proficiency_type: str = Field(sa_column=Column(String, nullable=False))
    proficiency_key: str = Field(sa_column=Column(String, nullable=False))
    label: str = Field(sa_column=Column(String, nullable=False))

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    )


class GrantSpell(SQLModel, table=True):
    """Declared spell grant."""

    __tablename__ = "grant_spells"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "owner_type",
            "owner_id",
            "spell_source_key",
            "label",
            name="uq_grant_spells_owner",
        ),
        Index("ix_grant_spells_owner", "owner_type", "owner_id"),
        Index("ix_grant_spells_spell_id", "spell_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="sources.id", index=True)
    owner_type: str = Field(sa_column=Column(String, nullable=False))
    owner_id: int = Field(sa_column=Column(Integer, nullable=False))
    spell_source_key: str = Field(sa_column=Column(String, nullable=False))
    label: str = Field(sa_column=Column(String, nullable=False))
    spell_id: Optional[int] = Field(default=None, foreign_key="spells.id")

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    )


class GrantFeature(SQLModel, table=True):
    """Declared feature grant."""

    __tablename__ = "grant_features"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "owner_type",
            "owner_id",
            "feature_source_key",
            "label",
            name="uq_grant_features_owner",
        ),
        Index("ix_grant_features_owner", "owner_type", "owner_id"),
        Index("ix_grant_features_feature_id", "feature_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="sources.id", index=True)
    owner_type: str = Field(sa_column=Column(String, nullable=False))
    owner_id: int = Field(sa_column=Column(Integer, nullable=False))
    feature_source_key: str = Field(sa_column=Column(String, nullable=False))
    label: str = Field(sa_column=Column(String, nullable=False))
    feature_id: Optional[int] = Field(default=None, foreign_key="features.id")

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    )
