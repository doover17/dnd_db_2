from __future__ import annotations

from pathlib import Path
import sys

from sqlalchemy import func
from sqlmodel import Session, select

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.db.upsert import upsert_raw_entity
from dnd_db.ingest.load_choices import load_choices
from dnd_db.models.choices import ChoiceGroup, ChoiceOption
from dnd_db.models.dnd_class import DndClass
from dnd_db.models.feature import Feature
from dnd_db.models.source import Source
from dnd_db.verify.choices import verify_choices


def _seed_choice_data(session: Session) -> None:
    source = Source(name="5e-bits", base_url="https://example.com")
    session.add(source)
    session.commit()
    session.refresh(source)

    class_payload = {
        "index": "rogue",
        "name": "Rogue",
        "proficiency_choices": [
            {
                "choose": 2,
                "type": "proficiency",
                "from": {
                    "options": [
                        {
                            "option_type": "reference",
                            "item": {
                                "index": "skill-acrobatics",
                                "name": "Acrobatics",
                                "type": "proficiency",
                            },
                        },
                        {
                            "option_type": "reference",
                            "item": {
                                "index": "skill-history",
                                "name": "History",
                                "type": "proficiency",
                            },
                        },
                    ]
                },
            }
        ],
    }
    feature_payload = {
        "index": "fighting-style",
        "name": "Fighting Style",
        "level": 1,
        "class": {"index": "fighter"},
        "choice": {
            "choose": 1,
            "type": "fighting_style",
            "from": {
                "options": [
                    {
                        "option_type": "reference",
                        "item": {
                            "index": "defense",
                            "name": "Defense",
                            "type": "feature",
                        },
                    },
                    {
                        "option_type": "reference",
                        "item": {
                            "index": "dueling",
                            "name": "Dueling",
                            "type": "feature",
                        },
                    },
                    {
                        "option_type": "reference",
                        "item": {
                            "index": "missing-style",
                            "name": "Missing Style",
                            "type": "feature",
                        },
                    },
                ]
            },
        },
    }

    raw_class, _, _ = upsert_raw_entity(
        session,
        source_id=source.id,
        entity_type="class",
        source_key="rogue",
        payload=class_payload,
        name=class_payload.get("name"),
    )
    raw_feature, _, _ = upsert_raw_entity(
        session,
        source_id=source.id,
        entity_type="feature",
        source_key="fighting-style",
        payload=feature_payload,
        name=feature_payload.get("name"),
    )

    session.add(
        DndClass(
            source_id=source.id,
            raw_entity_id=raw_class.id,
            source_key="rogue",
            name="Rogue",
        )
    )

    fighting_style = Feature(
        source_id=source.id,
        raw_entity_id=raw_feature.id,
        source_key="fighting-style",
        name="Fighting Style",
        level=1,
        class_source_key="fighter",
    )
    defense = Feature(
        source_id=source.id,
        raw_entity_id=raw_feature.id,
        source_key="defense",
        name="Defense",
        level=1,
        class_source_key="fighter",
    )
    dueling = Feature(
        source_id=source.id,
        raw_entity_id=raw_feature.id,
        source_key="dueling",
        name="Dueling",
        level=1,
        class_source_key="fighter",
    )
    session.add(fighting_style)
    session.add(defense)
    session.add(dueling)
    session.commit()


def test_load_choices_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "choices.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        _seed_choice_data(session)

    summary = load_choices(engine=engine, source_name="5e-bits")
    assert summary["choice_groups_created"] == 2
    assert summary["choice_options_created"] == 5
    assert summary["missing_option_refs_count"] == 1

    summary_again = load_choices(engine=engine, source_name="5e-bits")
    assert summary_again["choice_groups_created"] == 0
    assert summary_again["choice_options_created"] == 0

    with Session(engine) as session:
        group_count = session.exec(
            select(func.count()).select_from(ChoiceGroup)
        ).one()
        option_count = session.exec(
            select(func.count()).select_from(ChoiceOption)
        ).one()
        defense_option = session.exec(
            select(ChoiceOption).where(ChoiceOption.option_source_key == "defense")
        ).one()
    assert group_count == 2
    assert option_count == 5
    assert defense_option.option_ref_id is not None


def test_verify_choices_reports_issues(tmp_path: Path) -> None:
    db_path = tmp_path / "choices-verify.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        source = Source(name="5e-bits", base_url="https://example.com")
        session.add(source)
        session.commit()
        session.refresh(source)

        group = ChoiceGroup(
            source_id=source.id,
            owner_type="class",
            owner_id=999,
            choice_type="generic",
            choose_n=1,
        )
        session.add(group)
        session.commit()

        session.add(
            ChoiceOption(
                choice_group_id=999,
                option_type="feature",
                option_source_key="ghost",
                label="Ghost",
            )
        )
        session.commit()

        report = verify_choices(session)

    errors = report["errors"]
    assert any("missing class owner" in error for error in errors)
    assert any("Choice option missing group" in error for error in errors)
    assert any("Choice group has no options" in error for error in errors)
