from __future__ import annotations

from pathlib import Path
import sys
import json

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from sqlmodel import Session, select

from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.ingest.api_client import SrdApiClient
from dnd_db.ingest.import_conditions import import_conditions
from dnd_db.models.condition import Condition
from dnd_db.models.import_run import ImportRun
from dnd_db.models.raw_entity import RawEntity


def _payload(index: str, text: str) -> dict:
    return {
        "index": index,
        "name": index.replace("-", " ").title(),
        "desc": [text],
        "srd": True,
        "url": f"/api/conditions/{index}",
    }


def _stub_client(monkeypatch, payloads: dict[str, dict]) -> None:
    def _list_resources(self, resource: str) -> list[dict]:
        assert resource == "conditions"
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


def test_import_conditions_idempotent(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "conditions.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    payloads = {
        "blinded": _payload("blinded", "Cannot see."),
        "charmed": _payload("charmed", "Cannot attack charmer."),
    }
    _stub_client(monkeypatch, payloads)

    processed = import_conditions(engine=engine, base_url="https://example.com")
    assert processed == 2

    with Session(engine) as session:
        conditions = session.exec(select(Condition)).all()
        raw_conditions = session.exec(
            select(RawEntity).where(RawEntity.entity_type == "condition")
        ).all()
        run = session.exec(
            select(ImportRun).order_by(ImportRun.id.desc()).limit(1)
        ).one()

    assert len(conditions) == 2
    assert len(raw_conditions) == 2
    assert run.notes is not None

    processed = import_conditions(engine=engine, base_url="https://example.com")
    assert processed == 2

    with Session(engine) as session:
        run = session.exec(
            select(ImportRun).order_by(ImportRun.id.desc()).limit(1)
        ).one()
    notes = json.loads(run.notes)
    assert notes["raw_created"] == 0
    assert notes["raw_updated"] == 0
    assert notes["condition_created"] == 0
    assert notes["condition_updated"] == 0

    payloads["blinded"] = _payload("blinded", "Vision impaired.")
    _stub_client(monkeypatch, payloads)

    processed = import_conditions(engine=engine, base_url="https://example.com")
    assert processed == 2

    with Session(engine) as session:
        condition = session.exec(
            select(Condition).where(Condition.source_key == "blinded")
        ).one()
        run = session.exec(
            select(ImportRun).order_by(ImportRun.id.desc()).limit(1)
        ).one()

    assert condition.desc == "Vision impaired."
    notes = json.loads(run.notes)
    assert notes["raw_created"] == 0
    assert notes["raw_updated"] == 1
    assert notes["condition_created"] == 0
    assert notes["condition_updated"] == 1
