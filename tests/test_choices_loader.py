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
from dnd_db.models.spell import Spell
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


def test_load_choices_v2_types(tmp_path: Path) -> None:
    db_path = tmp_path / "choices-v2.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        source = Source(name="5e-bits", base_url="https://example.com")
        session.add(source)
        session.commit()
        session.refresh(source)

        wizard_payload = {
            "index": "wizard",
            "name": "Wizard",
            "spell_choices": [
                {
                    "type": "spell",
                    "choose": 2,
                    "from": [
                        {
                            "option_type": "spell",
                            "index": "magic-missile",
                            "name": "Magic Missile",
                        },
                        {
                            "option_type": "spell",
                            "index": "shield",
                            "name": "Shield",
                        },
                    ],
                }
            ],
        }

        raw_wizard, _, _ = upsert_raw_entity(
            session,
            source_id=source.id,
            entity_type="class",
            source_key="wizard",
            payload=wizard_payload,
            name=wizard_payload.get("name"),
        )

        session.add(
            DndClass(
                source_id=source.id,
                raw_entity_id=raw_wizard.id,
                source_key="wizard",
                name="Wizard",
            )
        )

        expertise_payload = {
            "index": "expertise",
            "name": "Expertise",
            "choices": [
                {
                    "name": "Expertise",
                    "choose": 2,
                    "from": [
                        {
                            "option_type": "reference",
                            "item": {
                                "index": "skill-acrobatics",
                                "name": "Skill: Acrobatics",
                                "type": "proficiency",
                            },
                        },
                        {
                            "option_type": "reference",
                            "item": {
                                "index": "skill-stealth",
                                "name": "Skill: Stealth",
                                "type": "proficiency",
                            },
                        },
                    ],
                }
            ],
        }

        raw_expertise, _, _ = upsert_raw_entity(
            session,
            source_id=source.id,
            entity_type="feature",
            source_key="expertise",
            payload=expertise_payload,
            name=expertise_payload.get("name"),
        )

        session.add(
            Feature(
                source_id=source.id,
                raw_entity_id=raw_expertise.id,
                source_key="expertise",
                name="Expertise",
                level=1,
                class_source_key="rogue",
            )
        )

        invocation_payload = {
            "index": "eldritch-invocations",
            "name": "Eldritch Invocations",
            "choices": [
                {
                    "name": "Eldritch Invocation",
                    "choose": 1,
                    "from": [
                        {
                            "option_type": "feature",
                            "index": "agonizing-blast",
                            "name": "Agonizing Blast",
                        }
                    ],
                }
            ],
        }

        raw_invocations, _, _ = upsert_raw_entity(
            session,
            source_id=source.id,
            entity_type="feature",
            source_key="eldritch-invocations",
            payload=invocation_payload,
            name=invocation_payload.get("name"),
        )

        session.add(
            Feature(
                source_id=source.id,
                raw_entity_id=raw_invocations.id,
                source_key="eldritch-invocations",
                name="Eldritch Invocations",
                level=2,
                class_source_key="warlock",
            )
        )
        session.add(
            Feature(
                source_id=source.id,
                raw_entity_id=None,
                source_key="agonizing-blast",
                name="Agonizing Blast",
                level=2,
                class_source_key="warlock",
            )
        )

        session.add_all(
            [
                Spell(
                    source_id=source.id,
                    raw_entity_id=None,
                    source_key="magic-missile",
                    name="Magic Missile",
                    level=1,
                ),
                Spell(
                    source_id=source.id,
                    raw_entity_id=None,
                    source_key="shield",
                    name="Shield",
                    level=1,
                ),
            ]
        )
        session.commit()

    summary = load_choices(engine=engine, source_name="5e-bits")
    assert summary["choice_groups_created"] == 3
    assert summary["choice_options_created"] == 5

    with Session(engine) as session:
        groups = session.exec(select(ChoiceGroup)).all()
        types = {group.choice_type for group in groups}
        assert {"spell", "expertise", "invocation"} <= types

        spell_options = session.exec(
            select(ChoiceOption).where(ChoiceOption.option_type == "spell")
        ).all()
        assert len(spell_options) == 2
