from __future__ import annotations

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from sqlmodel import Session

from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.models.choices import ChoiceGroup, Prerequisite
from dnd_db.models.dnd_class import DndClass
from dnd_db.models.feature import Feature
from dnd_db.models.source import Source
from dnd_db.verify.prereqs import verify_prereqs


def test_verify_prereqs_passes(tmp_path: Path) -> None:
    db_path = tmp_path / "prereqs-verify.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        source = Source(name="5e-bits", base_url="https://example.com")
        session.add(source)
        session.commit()
        session.refresh(source)

        fighter = DndClass(
            source_id=source.id,
            raw_entity_id=None,
            source_key="fighter",
            name="Fighter",
        )
        session.add(fighter)
        session.commit()
        session.refresh(fighter)

        feature = Feature(
            source_id=source.id,
            raw_entity_id=None,
            source_key="action-surge",
            name="Action Surge",
            level=2,
            class_source_key="fighter",
        )
        session.add(feature)
        session.commit()
        session.refresh(feature)

        group = ChoiceGroup(
            source_id=source.id,
            owner_type="class",
            owner_id=fighter.id,
            choice_type="generic",
            choose_n=1,
            level=1,
            label="Skill Proficiency",
            source_key="class:fighter:generic:1:skill-proficiency",
        )
        session.add(group)
        session.commit()
        session.refresh(group)

        session.add(
            Prerequisite(
                applies_to_type="feature",
                applies_to_id=feature.id,
                prereq_type="class",
                key="fighter",
                operator="==",
                value="true",
            )
        )
        session.add(
            Prerequisite(
                applies_to_type="choice_group",
                applies_to_id=group.id,
                prereq_type="class",
                key="fighter",
                operator="==",
                value="true",
            )
        )
        session.commit()

        report = verify_prereqs(session)

    assert report["errors"] == []


def test_verify_prereqs_missing_targets(tmp_path: Path) -> None:
    db_path = tmp_path / "prereqs-verify-missing.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        session.add(
            Prerequisite(
                applies_to_type="feature",
                applies_to_id=999,
                prereq_type="class",
                key="fighter",
                operator="==",
                value="true",
            )
        )
        session.commit()

        report = verify_prereqs(session)

    assert any("missing feature apply target" in error for error in report["errors"])
