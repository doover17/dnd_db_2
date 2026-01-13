"""Verification checks for grants."""

from __future__ import annotations

from sqlalchemy import func
from sqlmodel import Session, select

from dnd_db.models.dnd_class import DndClass
from dnd_db.models.feature import Feature
from dnd_db.models.grants import GrantFeature, GrantProficiency, GrantSpell
from dnd_db.models.spell import Spell
from dnd_db.models.subclass import Subclass


def verify_grants(session: Session) -> dict[str, list[str]]:
    """Verify grant integrity."""
    errors: list[str] = []
    warnings: list[str] = []

    duplicate_profs = session.exec(
        select(
            GrantProficiency.source_id,
            GrantProficiency.owner_type,
            GrantProficiency.owner_id,
            GrantProficiency.proficiency_type,
            GrantProficiency.proficiency_key,
            GrantProficiency.label,
            func.count(GrantProficiency.id),
        )
        .group_by(
            GrantProficiency.source_id,
            GrantProficiency.owner_type,
            GrantProficiency.owner_id,
            GrantProficiency.proficiency_type,
            GrantProficiency.proficiency_key,
            GrantProficiency.label,
        )
        .having(func.count(GrantProficiency.id) > 1)
    ).all()
    for (
        source_id,
        owner_type,
        owner_id,
        prof_type,
        prof_key,
        label,
        count,
    ) in duplicate_profs:
        errors.append(
            "Duplicate grant proficiency: "
            f"source_id={source_id} owner_type={owner_type} owner_id={owner_id} "
            f"type={prof_type} key={prof_key} label={label} count={count}"
        )

    duplicate_spells = session.exec(
        select(
            GrantSpell.source_id,
            GrantSpell.owner_type,
            GrantSpell.owner_id,
            GrantSpell.spell_source_key,
            GrantSpell.label,
            func.count(GrantSpell.id),
        )
        .group_by(
            GrantSpell.source_id,
            GrantSpell.owner_type,
            GrantSpell.owner_id,
            GrantSpell.spell_source_key,
            GrantSpell.label,
        )
        .having(func.count(GrantSpell.id) > 1)
    ).all()
    for source_id, owner_type, owner_id, spell_key, label, count in duplicate_spells:
        errors.append(
            "Duplicate grant spell: "
            f"source_id={source_id} owner_type={owner_type} owner_id={owner_id} "
            f"spell_source_key={spell_key} label={label} count={count}"
        )

    duplicate_features = session.exec(
        select(
            GrantFeature.source_id,
            GrantFeature.owner_type,
            GrantFeature.owner_id,
            GrantFeature.feature_source_key,
            GrantFeature.label,
            func.count(GrantFeature.id),
        )
        .group_by(
            GrantFeature.source_id,
            GrantFeature.owner_type,
            GrantFeature.owner_id,
            GrantFeature.feature_source_key,
            GrantFeature.label,
        )
        .having(func.count(GrantFeature.id) > 1)
    ).all()
    for source_id, owner_type, owner_id, feature_key, label, count in duplicate_features:
        errors.append(
            "Duplicate grant feature: "
            f"source_id={source_id} owner_type={owner_type} owner_id={owner_id} "
            f"feature_source_key={feature_key} label={label} count={count}"
        )

    missing_owner_class = session.exec(
        select(GrantProficiency).where(
            GrantProficiency.owner_type == "class",
            ~GrantProficiency.owner_id.in_(select(DndClass.id)),
        )
    ).all()
    for grant in missing_owner_class:
        errors.append(
            "Grant proficiency missing class owner: "
            f"id={grant.id} owner_id={grant.owner_id}"
        )

    missing_owner_feature = session.exec(
        select(GrantProficiency).where(
            GrantProficiency.owner_type == "feature",
            ~GrantProficiency.owner_id.in_(select(Feature.id)),
        )
    ).all()
    for grant in missing_owner_feature:
        errors.append(
            "Grant proficiency missing feature owner: "
            f"id={grant.id} owner_id={grant.owner_id}"
        )

    missing_owner_subclass = session.exec(
        select(GrantProficiency).where(
            GrantProficiency.owner_type == "subclass",
            ~GrantProficiency.owner_id.in_(select(Subclass.id)),
        )
    ).all()
    for grant in missing_owner_subclass:
        errors.append(
            "Grant proficiency missing subclass owner: "
            f"id={grant.id} owner_id={grant.owner_id}"
        )

    missing_spell_refs = session.exec(
        select(GrantSpell)
        .outerjoin(
            Spell,
            (Spell.source_key == GrantSpell.spell_source_key)
            & (Spell.source_id == GrantSpell.source_id),
        )
        .where(Spell.id.is_(None))
    ).all()
    for grant in missing_spell_refs:
        errors.append(
            "Grant spell missing spell reference: "
            f"id={grant.id} spell_source_key={grant.spell_source_key}"
        )

    missing_feature_refs = session.exec(
        select(GrantFeature)
        .outerjoin(
            Feature,
            (Feature.source_key == GrantFeature.feature_source_key)
            & (Feature.source_id == GrantFeature.source_id),
        )
        .where(Feature.id.is_(None))
    ).all()
    for grant in missing_feature_refs:
        errors.append(
            "Grant feature missing feature reference: "
            f"id={grant.id} feature_source_key={grant.feature_source_key}"
        )

    return {"errors": errors, "warnings": warnings}
