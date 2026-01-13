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


def _seed_choice_data(session: Session) -> dict[str, dict]:
    source = Source(name="5e-bits", base_url="https://example.com")
    session.add(source)
    session.commit()
    session.refresh(source)

    class_payload = {
        "index": "fighter",
        "name": "Fighter",
        "choices": [
            {
                "type": "fighting_style",
                "choose": 1,
                "from": [
                    {
                        "option_type": "feature",
                        "index": "fighting-style-archery",
                        "name": "Archery",
                    },
                    {
                        "option_type": "feature",
                        "index": "fighting-style-defense",
                        "name": "Defense",
                    },
                ],
            }
        ],
    }

    raw_class, _, _ = upsert_raw_entity(
        session,
        source_id=source.id,
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

    features = [
        Feature(
            source_id=source.id,
            raw_entity_id=None,
            source_key="fighting-style-archery",
            name="Archery",
            level=1,
            class_source_key="fighter",
        ),
        Feature(
            source_id=source.id,
            raw_entity_id=None,
            source_key="fighting-style-defense",
            name="Defense",
            level=1,
            class_source_key="fighter",
        ),
        Feature(
            source_id=source.id,
            raw_entity_id=None,
            source_key="fighting-style-dueling",
            name="Dueling",
            level=1,
            class_source_key="fighter",
        ),
    ]
    session.add_all(features)
    session.commit()
    return {"source_id": source.id, "class_payload": class_payload}


def test_load_choices_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "choices.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        seed_data = _seed_choice_data(session)

    summary = load_choices(engine=engine, source_name="5e-bits")
    assert summary["choice_groups_created"] == 1
    assert summary["choice_options_created"] == 2
    assert summary["unresolved_feature_refs"] == 0

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
    assert group_count == 1
    assert option_count == 2

    updated_payload = {
        **seed_data["class_payload"],
        "choices": [
            {
                "type": "fighting_style",
                "choose": 1,
                "from": [
                    {
                        "option_type": "feature",
                        "index": "fighting-style-archery",
                        "name": "Archery",
                    },
                    {
                        "option_type": "feature",
                        "index": "fighting-style-defense",
                        "name": "Defense",
                    },
                    {
                        "option_type": "feature",
                        "index": "fighting-style-dueling",
                        "name": "Dueling",
                    },
                ],
            }
        ],
    }

    with Session(engine) as session:
        upsert_raw_entity(
            session,
            source_id=seed_data["source_id"],
            entity_type="class",
            source_key="fighter",
            payload=updated_payload,
            name=updated_payload.get("name"),
        )

    summary_third = load_choices(engine=engine, source_name="5e-bits")
    assert summary_third["choice_groups_created"] == 0
    assert summary_third["choice_options_created"] == 1
