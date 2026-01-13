"""Character storage models (no rule enforcement)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Character(SQLModel, table=True):
    """Represents a character record."""

    __tablename__ = "characters"
    __table_args__ = (Index("ix_characters_name", "name"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String, nullable=False))
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


class CharacterLevel(SQLModel, table=True):
    """Tracks a character's class/subclass at a given level."""

    __tablename__ = "character_levels"
    __table_args__ = (
        UniqueConstraint(
            "character_id", "level", name="uq_character_levels_character_level"
        ),
        Index("ix_character_levels_character", "character_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    character_id: int = Field(foreign_key="characters.id", index=True)
    class_id: int = Field(foreign_key="classes.id", index=True)
    subclass_id: Optional[int] = Field(
        default=None, foreign_key="subclasses.id", index=True
    )
    level: int = Field(sa_column=Column(Integer, nullable=False))

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    )


class CharacterChoice(SQLModel, table=True):
    """Stores a character's choice selection."""

    __tablename__ = "character_choices"
    __table_args__ = (
        Index("ix_character_choices_character", "character_id"),
        Index("ix_character_choices_group", "choice_group_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    character_id: int = Field(foreign_key="characters.id", index=True)
    choice_group_id: int = Field(foreign_key="choice_groups.id", index=True)
    choice_option_id: Optional[int] = Field(
        default=None, foreign_key="choice_options.id", index=True
    )
    option_label: Optional[str] = Field(
        default=None, sa_column=Column(String, nullable=True)
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    )


class CharacterFeature(SQLModel, table=True):
    """Stores a character's acquired feature."""

    __tablename__ = "character_features"
    __table_args__ = (
        UniqueConstraint(
            "character_id", "feature_id", name="uq_character_features_character_feature"
        ),
        Index("ix_character_features_character", "character_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    character_id: int = Field(foreign_key="characters.id", index=True)
    feature_id: int = Field(foreign_key="features.id", index=True)

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    )


class CharacterKnownSpell(SQLModel, table=True):
    """Stores a character's known spell."""

    __tablename__ = "character_known_spells"
    __table_args__ = (
        UniqueConstraint(
            "character_id", "spell_id", name="uq_character_known_spells_character_spell"
        ),
        Index("ix_character_known_spells_character", "character_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    character_id: int = Field(foreign_key="characters.id", index=True)
    spell_id: int = Field(foreign_key="spells.id", index=True)

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    )


class CharacterPreparedSpell(SQLModel, table=True):
    """Stores a character's prepared spell."""

    __tablename__ = "character_prepared_spells"
    __table_args__ = (
        UniqueConstraint(
            "character_id",
            "spell_id",
            name="uq_character_prepared_spells_character_spell",
        ),
        Index("ix_character_prepared_spells_character", "character_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    character_id: int = Field(foreign_key="characters.id", index=True)
    spell_id: int = Field(foreign_key="spells.id", index=True)

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    )


class InventoryItem(SQLModel, table=True):
    """Stores a character's inventory item."""

    __tablename__ = "inventory_items"
    __table_args__ = (
        UniqueConstraint(
            "character_id", "name", name="uq_inventory_items_character_name"
        ),
        Index("ix_inventory_items_character", "character_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    character_id: int = Field(foreign_key="characters.id", index=True)
    name: str = Field(sa_column=Column(String, nullable=False))
    quantity: int = Field(default=1, sa_column=Column(Integer, nullable=False))
    notes: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    )
