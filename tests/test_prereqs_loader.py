from __future__ import annotations

from pathlib import Path
import sys

from sqlalchemy import func
from sqlmodel import Session, select

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.db.upsert import upsert_raw_entity
from dnd_db.ingest.load_choices import load_choices
from dnd_db.ingest.load_prereqs import load_prereqs
from dnd_db.models.choices import ChoiceGroup, Prerequisite
from dnd_db.models.dnd_class import DndClass
from dnd_db.models.feature import Feature
from dnd_db.models.source import Source


def test_load_prereqs_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "prereqs.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        source = Source(name="5e-bits", base_url="https://example.com")
        session.add(source)
        session.commit()
        session.refresh(source)
        source_id = source.id

        class_payload = {
            "index": "fighter",
            "name": "Fighter",
            "choices": [
                {
                    "name": "Skill Proficiency",
                    "choose": 1,
                    "from": ["Athletics", "Acrobatics"],
                    "prerequisites": [
                        {
                            "type": "ability_score",
                            "ability_score": {"index": "str"},
                            "minimum_score": 13,
                        }
                    ],
                }
            ],
        }

        raw_class, _, _ = upsert_raw_entity(
            session,
            source_id=source_id,
            entity_type="class",
            source_key="fighter",
            payload=class_payload,
            name=class_payload.get("name"),
        )

        session.add(
            DndClass(
                source_id=source.id,
                raw_entity_id=raw_class.id,
                source_key="fighter",
                name="Fighter",
            )
        )

        feature_payload = {
            "index": "action-surge",
            "name": "Action Surge",
            "prerequisites": [
                {"type": "level", "level": 2, "class": {"index": "fighter"}},
                {
                    "type": "ability_score",
                    "ability_score": {"index": "str"},
                    "minimum_score": 13,
                },
                {"type": "feature", "feature": {"index": "second-wind"}},
            ],
        }

        raw_feature, _, _ = upsert_raw_entity(
            session,
            source_id=source_id,
            entity_type="feature",
            source_key="action-surge",
            payload=feature_payload,
            name=feature_payload.get("name"),
        )

        session.add_all(
            [
                Feature(
                    source_id=source_id,
                    raw_entity_id=raw_feature.id,
                    source_key="action-surge",
                    name="Action Surge",
                    level=2,
                    class_source_key="fighter",
                ),
                Feature(
                    source_id=source_id,
                    raw_entity_id=None,
                    source_key="second-wind",
                    name="Second Wind",
                    level=1,
                    class_source_key="fighter",
                ),
            ]
        )
        session.commit()

    load_choices(engine=engine, source_name="5e-bits")

    summary = load_prereqs(engine=engine, source_name="5e-bits")
    assert summary["prereqs_created"] == 4
    assert summary["missing_refs"] == 0

    summary_again = load_prereqs(engine=engine, source_name="5e-bits")
    assert summary_again["prereqs_created"] == 0

    with Session(engine) as session:
        total = session.exec(select(func.count()).select_from(Prerequisite)).one()
        group_count = session.exec(
            select(func.count())
            .select_from(Prerequisite)
            .where(Prerequisite.applies_to_type == "choice_group")
        ).one()
    assert total == 4
    assert group_count == 1

    updated_payload = {
        **feature_payload,
        "prerequisites": [
            *feature_payload["prerequisites"],
            {"type": "class", "class": {"index": "fighter"}},
        ],
    }

    with Session(engine) as session:
        upsert_raw_entity(
            session,
                source_id=source_id,
            entity_type="feature",
            source_key="action-surge",
            payload=updated_payload,
            name=updated_payload.get("name"),
        )

    summary_third = load_prereqs(engine=engine, source_name="5e-bits")
    assert summary_third["prereqs_created"] == 1
