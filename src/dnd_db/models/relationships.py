"""Relationship join table models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime, Index, Integer, UniqueConstraint
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ClassFeatureLink(SQLModel, table=True):
    """Join class -> feature with optional level context."""

    __tablename__ = "class_features"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "class_id",
            "feature_id",
            "level",
            name="uq_class_features_source_class_feature_level",
        ),
        Index("ix_class_features_class_id", "class_id"),
        Index("ix_class_features_feature_id", "feature_id"),
        Index("ix_class_features_class_level", "class_id", "level"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="sources.id", index=True)
    class_id: int = Field(foreign_key="classes.id")
    feature_id: int = Field(foreign_key="features.id")
    level: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    )


class SubclassFeatureLink(SQLModel, table=True):
    """Join subclass -> feature with optional level context."""

    __tablename__ = "subclass_features"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "subclass_id",
            "feature_id",
            "level",
            name="uq_subclass_features_source_subclass_feature_level",
        ),
        Index("ix_subclass_features_subclass_id", "subclass_id"),
        Index("ix_subclass_features_feature_id", "feature_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="sources.id", index=True)
    subclass_id: int = Field(foreign_key="subclasses.id")
    feature_id: int = Field(foreign_key="features.id")
    level: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    )


class SpellClassLink(SQLModel, table=True):
    """Join spell -> class."""

    __tablename__ = "spell_classes"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "spell_id",
            "class_id",
            name="uq_spell_classes_source_spell_class",
        ),
        Index("ix_spell_classes_spell_id", "spell_id"),
        Index("ix_spell_classes_class_id", "class_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="sources.id", index=True)
    spell_id: int = Field(foreign_key="spells.id")
    class_id: int = Field(foreign_key="classes.id")
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    )
