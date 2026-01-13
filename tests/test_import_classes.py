from __future__ import annotations

from pathlib import Path
import sys
import json

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from sqlmodel import Session, select

from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.ingest.api_client import SrdApiClient
from dnd_db.ingest.import_classes import import_classes
from dnd_db.models.dnd_class import DndClass
from dnd_db.models.import_run import ImportRun
from dnd_db.models.raw_entity import RawEntity
from dnd_db.verify.checks import run_all_checks


def _payload(index: str, hit_die: int) -> dict:
    return {
        "index": index,
        "name": index.replace("-", " ").title(),
        "hit_die": hit_die,
        "proficiencies": [{"index": "light-armor", "name": "Light Armor"}],
        "saving_throws": [{"index": "str", "name": "STR"}],
        "starting_equipment": [
            {"equipment": {"index": "club", "name": "Club"}, "quantity": 1}
        ],
        "spellcasting": {"spellcasting_ability": {"index": "cha", "name": "CHA"}},
        "srd": True,
        "url": f"/api/classes/{index}",
    }


def _stub_client(monkeypatch, payloads: dict[str, dict]) -> None:
    def _list_resources(self, resource: str) -> list[dict]:
        assert resource == "classes"
        return [
            {"index": key, "url": payload["url"], "name": payload["name"]}
            for key, payload in payloads.items()
        ]

    def _get_by_url(self, url: str) -> dict:
        for payload in payloads.values():
            if payload["url"] == url:
                return payload
        raise KeyError(url)

    monkeypatch.setattr(SrdApiClient, "list_resources", _list_resources)
    monkeypatch.setattr(SrdApiClient, "get_by_url", _get_by_url)


def test_import_classes_idempotent(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "classes.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    payloads = {
        "barbarian": _payload("barbarian", 12),
        "bard": _payload("bard", 8),
    }
    _stub_client(monkeypatch, payloads)

    processed = import_classes(engine=engine, base_url="https://example.com")
    assert processed == 2

    with Session(engine) as session:
        classes = session.exec(select(DndClass)).all()
        raw_classes = session.exec(
            select(RawEntity).where(RawEntity.entity_type == "class")
        ).all()
        runs = session.exec(select(ImportRun).order_by(ImportRun.id)).all()
        ok, report = run_all_checks(session)

    assert len(classes) == 2
    assert len(raw_classes) == 2
    assert runs[-1].status == "success"
    assert ok is True
    assert report["errors"] == []

    processed = import_classes(engine=engine, base_url="https://example.com")
    assert processed == 2

    with Session(engine) as session:
        classes = session.exec(select(DndClass)).all()
        raw_classes = session.exec(
            select(RawEntity).where(RawEntity.entity_type == "class")
        ).all()
        run = session.exec(
            select(ImportRun).order_by(ImportRun.id.desc()).limit(1)
        ).one()

    assert len(classes) == 2
    assert len(raw_classes) == 2
    assert run.notes is not None
    notes = json.loads(run.notes)
    assert notes["raw_created"] == 0
    assert notes["raw_updated"] == 0
    assert notes["class_created"] == 0
    assert notes["class_updated"] == 0

    payloads["barbarian"] = _payload("barbarian", 10)
    _stub_client(monkeypatch, payloads)

    processed = import_classes(engine=engine, base_url="https://example.com")
    assert processed == 2

    with Session(engine) as session:
        character_class = session.exec(
            select(DndClass).where(DndClass.source_key == "barbarian")
        ).one()
        run = session.exec(
            select(ImportRun).order_by(ImportRun.id.desc()).limit(1)
        ).one()

    assert character_class.hit_die == 10
    assert json.loads(character_class.saves) == ["STR"]
    assert json.loads(character_class.proficiencies) == ["Light Armor"]
    assert json.loads(character_class.starting_equipment) == [
        {"equipment": "Club", "quantity": 1}
    ]
    notes = json.loads(run.notes)
    assert notes["raw_created"] == 0
    assert notes["raw_updated"] == 1
    assert notes["class_created"] == 0
    assert notes["class_updated"] == 1
