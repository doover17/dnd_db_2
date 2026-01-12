from __future__ import annotations

from pathlib import Path
import sys
import json

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from sqlmodel import Session, select

from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.ingest.api_client import SrdApiClient
from dnd_db.ingest.import_spells import import_spells
from dnd_db.models.import_run import ImportRun
from dnd_db.models.raw_entity import RawEntity
from dnd_db.models.spell import Spell


def _payload(index: str, level: int) -> dict:
    return {
        "index": index,
        "name": index.replace("-", " ").title(),
        "level": level,
        "school": {"index": "evocation", "name": "Evocation"},
        "casting_time": "1 action",
        "range": "60 feet",
        "duration": "Instantaneous",
        "concentration": False,
        "ritual": False,
        "desc": ["Line 1", "Line 2"],
        "higher_level": ["More power"],
        "components": ["V", "S"],
        "material": "A bit of gum arabic",
        "srd": True,
        "url": f"/api/spells/{index}",
    }


def _stub_client(monkeypatch, payloads: dict[str, dict]) -> None:
    def _list_resources(self, resource: str) -> list[dict]:
        assert resource == "spells"
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


def test_import_spells_idempotent(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "spells.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    payloads = {
        "acid-arrow": _payload("acid-arrow", 2),
        "alarm": _payload("alarm", 1),
    }
    _stub_client(monkeypatch, payloads)

    processed = import_spells(engine=engine, base_url="https://example.com")
    assert processed == 2

    with Session(engine) as session:
        spells = session.exec(select(Spell)).all()
        raw_spells = session.exec(
            select(RawEntity).where(RawEntity.entity_type == "spell")
        ).all()
        runs = session.exec(select(ImportRun).order_by(ImportRun.id)).all()

    assert len(spells) == 2
    assert len(raw_spells) == 2
    assert runs[-1].status == "success"

    processed = import_spells(engine=engine, base_url="https://example.com")
    assert processed == 2

    with Session(engine) as session:
        spells = session.exec(select(Spell)).all()
        raw_spells = session.exec(
            select(RawEntity).where(RawEntity.entity_type == "spell")
        ).all()
        run = session.exec(
            select(ImportRun).order_by(ImportRun.id.desc()).limit(1)
        ).one()

    assert len(spells) == 2
    assert len(raw_spells) == 2
    assert run.notes is not None
    notes = json.loads(run.notes)
    assert notes["raw_created"] == 0
    assert notes["raw_updated"] == 0
    assert notes["spell_created"] == 0
    assert notes["spell_updated"] == 0

    payloads["acid-arrow"] = _payload("acid-arrow", 3)
    _stub_client(monkeypatch, payloads)

    processed = import_spells(engine=engine, base_url="https://example.com")
    assert processed == 2

    with Session(engine) as session:
        spell = session.exec(select(Spell).where(Spell.source_key == "acid-arrow")).one()
        run = session.exec(
            select(ImportRun).order_by(ImportRun.id.desc()).limit(1)
        ).one()

    assert spell.level == 3
    notes = json.loads(run.notes)
    assert notes["raw_created"] == 0
    assert notes["raw_updated"] == 1
    assert notes["spell_created"] == 0
    assert notes["spell_updated"] == 1
