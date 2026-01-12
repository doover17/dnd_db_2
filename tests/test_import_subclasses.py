from __future__ import annotations

from pathlib import Path
import sys
import json

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from sqlmodel import Session, select

from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.ingest.api_client import SrdApiClient
from dnd_db.ingest.import_subclasses import import_subclasses
from dnd_db.models.import_run import ImportRun
from dnd_db.models.raw_entity import RawEntity
from dnd_db.models.subclass import Subclass
from dnd_db.verify.checks import run_all_checks


def _payload(index: str, flavor: str) -> dict:
    return {
        "index": index,
        "name": index.replace("-", " ").title(),
        "class": {"index": "fighter", "name": "Fighter"},
        "subclass_flavor": flavor,
        "desc": ["First line", "Second line"],
        "spellcasting_ability": {"index": "int", "name": "INT"},
        "srd": True,
        "url": f"/api/subclasses/{index}",
    }


def _stub_client(monkeypatch, payloads: dict[str, dict]) -> None:
    def _list_resources(self, resource: str) -> list[dict]:
        assert resource == "subclasses"
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


def test_import_subclasses_idempotent(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "subclasses.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    payloads = {
        "champion": _payload("champion", "Martial Archetype"),
        "evocation": _payload("evocation", "Arcane Tradition"),
    }
    _stub_client(monkeypatch, payloads)

    processed = import_subclasses(engine=engine, base_url="https://example.com")
    assert processed == 2

    with Session(engine) as session:
        subclasses = session.exec(select(Subclass)).all()
        raw_subclasses = session.exec(
            select(RawEntity).where(RawEntity.entity_type == "subclass")
        ).all()
        runs = session.exec(select(ImportRun).order_by(ImportRun.id)).all()
        ok, report = run_all_checks(session)

    assert len(subclasses) == 2
    assert len(raw_subclasses) == 2
    assert runs[-1].status == "success"
    assert ok is True
    assert report["errors"] == []

    processed = import_subclasses(engine=engine, base_url="https://example.com")
    assert processed == 2

    with Session(engine) as session:
        subclasses = session.exec(select(Subclass)).all()
        raw_subclasses = session.exec(
            select(RawEntity).where(RawEntity.entity_type == "subclass")
        ).all()
        run = session.exec(
            select(ImportRun).order_by(ImportRun.id.desc()).limit(1)
        ).one()

    assert len(subclasses) == 2
    assert len(raw_subclasses) == 2
    assert run.notes is not None
    notes = json.loads(run.notes)
    assert notes["raw_created"] == 0
    assert notes["raw_updated"] == 0
    assert notes["subclass_created"] == 0
    assert notes["subclass_updated"] == 0

    payloads["champion"] = _payload("champion", "New Flavor")
    _stub_client(monkeypatch, payloads)

    processed = import_subclasses(engine=engine, base_url="https://example.com")
    assert processed == 2

    with Session(engine) as session:
        subclass = session.exec(
            select(Subclass).where(Subclass.source_key == "champion")
        ).one()
        run = session.exec(
            select(ImportRun).order_by(ImportRun.id.desc()).limit(1)
        ).one()

    assert subclass.subclass_flavor == "New Flavor"
    notes = json.loads(run.notes)
    assert notes["raw_created"] == 0
    assert notes["raw_updated"] == 1
    assert notes["subclass_created"] == 0
    assert notes["subclass_updated"] == 1
