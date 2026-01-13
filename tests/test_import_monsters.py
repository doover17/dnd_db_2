from __future__ import annotations

from pathlib import Path
import sys
import json

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from sqlmodel import Session, select

from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.ingest.api_client import SrdApiClient
from dnd_db.ingest.import_monsters import import_monsters
from dnd_db.models.import_run import ImportRun
from dnd_db.models.monster import Monster
from dnd_db.models.raw_entity import RawEntity


def _payload(index: str, hp: int) -> dict:
    return {
        "index": index,
        "name": index.replace("-", " ").title(),
        "size": "Medium",
        "type": "humanoid",
        "alignment": "neutral",
        "challenge_rating": 1,
        "hit_points": hp,
        "armor_class": 12,
        "speed": {"walk": "30 ft."},
        "srd": True,
        "url": f"/api/monsters/{index}",
    }


def _stub_client(monkeypatch, payloads: dict[str, dict]) -> None:
    def _list_resources(self, resource: str) -> list[dict]:
        assert resource == "monsters"
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


def test_import_monsters_idempotent(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "monsters.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    payloads = {
        "guard": _payload("guard", 11),
        "bandit": _payload("bandit", 12),
    }
    _stub_client(monkeypatch, payloads)

    processed = import_monsters(engine=engine, base_url="https://example.com")
    assert processed == 2

    with Session(engine) as session:
        monsters = session.exec(select(Monster)).all()
        raw_monsters = session.exec(
            select(RawEntity).where(RawEntity.entity_type == "monster")
        ).all()
        run = session.exec(
            select(ImportRun).order_by(ImportRun.id.desc()).limit(1)
        ).one()

    assert len(monsters) == 2
    assert len(raw_monsters) == 2
    assert run.notes is not None

    processed = import_monsters(engine=engine, base_url="https://example.com")
    assert processed == 2

    with Session(engine) as session:
        run = session.exec(
            select(ImportRun).order_by(ImportRun.id.desc()).limit(1)
        ).one()
    notes = json.loads(run.notes)
    assert notes["raw_created"] == 0
    assert notes["raw_updated"] == 0
    assert notes["monster_created"] == 0
    assert notes["monster_updated"] == 0

    payloads["guard"] = _payload("guard", 20)
    _stub_client(monkeypatch, payloads)

    processed = import_monsters(engine=engine, base_url="https://example.com")
    assert processed == 2

    with Session(engine) as session:
        monster = session.exec(
            select(Monster).where(Monster.source_key == "guard")
        ).one()
        run = session.exec(
            select(ImportRun).order_by(ImportRun.id.desc()).limit(1)
        ).one()

    assert monster.hit_points == 20
    notes = json.loads(run.notes)
    assert notes["raw_created"] == 0
    assert notes["raw_updated"] == 1
    assert notes["monster_created"] == 0
    assert notes["monster_updated"] == 1
