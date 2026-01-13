from __future__ import annotations

from pathlib import Path
import sys

from sqlmodel import Session

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.models.choices import ChoiceGroup, ChoiceOption
from dnd_db.models.dnd_class import DndClass
from dnd_db.models.feature import Feature
from dnd_db.models.relationships import (
    ClassFeatureLink,
    SpellClassLink,
    SubclassFeatureLink,
)
from dnd_db.models.source import Source
from dnd_db.models.spell import Spell
from dnd_db.models.subclass import Subclass
from dnd_db.queries import (
    get_all_available_features,
    get_choices_for_class_at_level,
    get_class_features_at_level,
    get_spell_list_for_class,
    get_subclass_features_at_level,
)


def _seed_query_data(session: Session) -> dict[str, int]:
    source = Source(name="5e-bits", base_url="https://example.com")
    session.add(source)
    session.commit()
    session.refresh(source)

    fighter = DndClass(
        source_id=source.id,
        source_key="fighter",
        name="Fighter",
        hit_die=10,
    )
    session.add(fighter)

    champion = Subclass(
        source_id=source.id,
        source_key="champion",
        name="Champion",
        class_source_key="fighter",
    )
    session.add(champion)

    fighting_style = Feature(
        source_id=source.id,
        source_key="fighting-style",
        name="Fighting Style",
        level=1,
        class_source_key="fighter",
    )
    second_wind = Feature(
        source_id=source.id,
        source_key="second-wind",
        name="Second Wind",
        level=1,
        class_source_key="fighter",
    )
    action_surge = Feature(
        source_id=source.id,
        source_key="action-surge",
        name="Action Surge",
        level=2,
        class_source_key="fighter",
    )
    improved_critical = Feature(
        source_id=source.id,
        source_key="improved-critical",
        name="Improved Critical",
        level=3,
        subclass_source_key="champion",
    )
    session.add(fighting_style)
    session.add(second_wind)
    session.add(action_surge)
    session.add(improved_critical)

    magic_missile = Spell(
        source_id=source.id,
        source_key="magic-missile",
        name="Magic Missile",
        level=1,
        concentration=False,
        ritual=False,
    )
    shield = Spell(
        source_id=source.id,
        source_key="shield",
        name="Shield",
        level=1,
        concentration=False,
        ritual=False,
    )
    session.add(magic_missile)
    session.add(shield)
    session.commit()

    session.add(
        ClassFeatureLink(
            source_id=source.id,
            class_id=fighter.id,
            feature_id=fighting_style.id,
            level=1,
        )
    )
    session.add(
        ClassFeatureLink(
            source_id=source.id,
            class_id=fighter.id,
            feature_id=second_wind.id,
            level=1,
        )
    )
    session.add(
        ClassFeatureLink(
            source_id=source.id,
            class_id=fighter.id,
            feature_id=action_surge.id,
            level=2,
        )
    )
    session.add(
        SubclassFeatureLink(
            source_id=source.id,
            subclass_id=champion.id,
            feature_id=improved_critical.id,
            level=3,
        )
    )
    session.add(
        SpellClassLink(
            source_id=source.id,
            spell_id=magic_missile.id,
            class_id=fighter.id,
        )
    )
    session.add(
        SpellClassLink(
            source_id=source.id,
            spell_id=shield.id,
            class_id=fighter.id,
        )
    )

    group = ChoiceGroup(
        source_id=source.id,
        owner_type="class",
        owner_id=fighter.id,
        choice_type="fighting_style",
        choose_n=1,
        level=1,
        label="Fighting Style",
        notes="Choose a fighting style",
        source_key="class:fighter:fighting_style:1:fighting-style",
    )
    session.add(group)
    session.commit()
    session.refresh(group)

    options = [
        ChoiceOption(
            choice_group_id=group.id,
            option_type="feature",
            option_source_key="defense",
            label="Defense",
            feature_id=None,
        ),
        ChoiceOption(
            choice_group_id=group.id,
            option_type="feature",
            option_source_key="dueling",
            label="Dueling",
            feature_id=None,
        ),
    ]
    session.add_all(options)
    session.commit()

    return {"class_id": fighter.id, "subclass_id": champion.id}


def test_queries(tmp_path: Path) -> None:
    db_path = tmp_path / "queries.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    with Session(engine) as session:
        ids = _seed_query_data(session)

    with Session(engine) as session:
        class_features = get_class_features_at_level(session, ids["class_id"], 1)
        assert class_features == [
            {
                "id": class_features[0]["id"],
                "source_key": "fighting-style",
                "name": "Fighting Style",
                "level": 1,
                "desc": None,
            },
            {
                "id": class_features[1]["id"],
                "source_key": "second-wind",
                "name": "Second Wind",
                "level": 1,
                "desc": None,
            },
        ]

        subclass_features = get_subclass_features_at_level(
            session, ids["subclass_id"], 3
        )
        assert subclass_features == [
            {
                "id": subclass_features[0]["id"],
                "source_key": "improved-critical",
                "name": "Improved Critical",
                "level": 3,
                "desc": None,
            }
        ]

        spells = get_spell_list_for_class(session, ids["class_id"])
        assert spells == [
            {
                "id": spells[0]["id"],
                "source_key": "magic-missile",
                "name": "Magic Missile",
                "level": 1,
                "school": None,
            },
            {
                "id": spells[1]["id"],
                "source_key": "shield",
                "name": "Shield",
                "level": 1,
                "school": None,
            },
        ]

        choices = get_choices_for_class_at_level(session, ids["class_id"], 1)
        assert choices == [
            {
                "id": choices[0]["id"],
                "choice_type": "fighting_style",
                "choose_n": 1,
                "level": 1,
                "label": "Fighting Style",
                "notes": "Choose a fighting style",
                "source_key": "class:fighter:fighting_style:1:fighting-style",
                "options": [
                    {
                        "id": choices[0]["options"][0]["id"],
                        "option_type": "feature",
                        "option_source_key": "defense",
                        "feature_id": None,
                        "label": "Defense",
                    },
                    {
                        "id": choices[0]["options"][1]["id"],
                        "option_type": "feature",
                        "option_source_key": "dueling",
                        "feature_id": None,
                        "label": "Dueling",
                    },
                ],
            }
        ]

        all_features = get_all_available_features(
            session, ids["class_id"], ids["subclass_id"], 3
        )
        assert all_features == {
            "class_features": [
                {
                    "id": all_features["class_features"][0]["id"],
                    "source_key": "fighting-style",
                    "name": "Fighting Style",
                    "level": 1,
                    "desc": None,
                },
                {
                    "id": all_features["class_features"][1]["id"],
                    "source_key": "second-wind",
                    "name": "Second Wind",
                    "level": 1,
                    "desc": None,
                },
                {
                    "id": all_features["class_features"][2]["id"],
                    "source_key": "action-surge",
                    "name": "Action Surge",
                    "level": 2,
                    "desc": None,
                },
            ],
            "subclass_features": [
                {
                    "id": all_features["subclass_features"][0]["id"],
                    "source_key": "improved-critical",
                    "name": "Improved Critical",
                    "level": 3,
                    "desc": None,
                }
            ],
        }
