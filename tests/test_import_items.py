from __future__ import annotations

from pathlib import Path
import sys
import json

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from sqlmodel import Session, select

from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.ingest.api_client import SrdApiClient
from dnd_db.ingest.import_items import import_items
from dnd_db.models.import_run import ImportRun
from dnd_db.models.item import Item
from dnd_db.models.raw_entity import RawEntity


def _payload(index: str, weight: float) -> dict:
    return {
        "index": index,
        "name": index.replace("-", " ").title(),
        "equipment_category": {"index": "adventuring-gear", "name": "Adventuring Gear"},
        "gear_category": {"index": "standard", "name": "Standard Gear"},
        "cost": {"quantity": 5, "unit": "gp"},
        "weight": weight,
        "desc": ["Item line 1", "Item line 2"],
        "srd": True,
        "url": f"/api/equipment/{index}",
    }


def _stub_client(monkeypatch, payloads: dict[str, dict]) -> None:
    def _list_resources(self, resource: str) -> list[dict]:
        assert resource == "equipment"
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


def test_import_items_idempotent(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "items.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    payloads = {
        "healers-kit": _payload("healers-kit", 3.0),
        "rope-hempen": _payload("rope-hempen", 10.0),
    }
    _stub_client(monkeypatch, payloads)

    processed = import_items(engine=engine, base_url="https://example.com")
    assert processed == 2

    with Session(engine) as session:
        items = session.exec(select(Item)).all()
        raw_items = session.exec(
            select(RawEntity).where(RawEntity.entity_type == "equipment")
        ).all()
        run = session.exec(
            select(ImportRun).order_by(ImportRun.id.desc()).limit(1)
        ).one()

    assert len(items) == 2
    assert len(raw_items) == 2
    assert run.notes is not None

    processed = import_items(engine=engine, base_url="https://example.com")
    assert processed == 2

    with Session(engine) as session:
        run = session.exec(
            select(ImportRun).order_by(ImportRun.id.desc()).limit(1)
        ).one()
    notes = json.loads(run.notes)
    assert notes["raw_created"] == 0
    assert notes["raw_updated"] == 0
    assert notes["item_created"] == 0
    assert notes["item_updated"] == 0

    payloads["healers-kit"] = _payload("healers-kit", 4.0)
    _stub_client(monkeypatch, payloads)

    processed = import_items(engine=engine, base_url="https://example.com")
    assert processed == 2

    with Session(engine) as session:
        item = session.exec(
            select(Item).where(Item.source_key == "healers-kit")
        ).one()
        run = session.exec(
            select(ImportRun).order_by(ImportRun.id.desc()).limit(1)
        ).one()

    assert item.weight == 4.0
    notes = json.loads(run.notes)
    assert notes["raw_created"] == 0
    assert notes["raw_updated"] == 1
    assert notes["item_created"] == 0
    assert notes["item_updated"] == 1
