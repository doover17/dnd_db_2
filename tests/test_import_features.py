from __future__ import annotations

from pathlib import Path
import sys
import json

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from sqlmodel import Session, select

from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.ingest.api_client import SrdApiClient
from dnd_db.ingest.import_features import import_features
from dnd_db.models.feature import Feature
from dnd_db.models.import_run import ImportRun
from dnd_db.models.raw_entity import RawEntity
from dnd_db.verify.checks import run_all_checks


def _payload(index: str, level: int) -> dict:
    return {
        "index": index,
        "name": index.replace("-", " ").title(),
        "level": level,
        "class": {"index": "rogue", "name": "Rogue"},
        "subclass": {"index": "thief", "name": "Thief"},
        "desc": ["Feature line 1", "Feature line 2"],
        "srd": True,
        "url": f"/api/features/{index}",
    }


def _stub_client(monkeypatch, payloads: dict[str, dict]) -> None:
    def _list_resources(self, resource: str) -> list[dict]:
        assert resource == "features"
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


def test_import_features_idempotent(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "features.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    payloads = {
        "cunning-action": _payload("cunning-action", 2),
        "sneak-attack": _payload("sneak-attack", 1),
    }
    _stub_client(monkeypatch, payloads)

    processed = import_features(engine=engine, base_url="https://example.com")
    assert processed == 2

    with Session(engine) as session:
        features = session.exec(select(Feature)).all()
        raw_features = session.exec(
            select(RawEntity).where(RawEntity.entity_type == "feature")
        ).all()
        runs = session.exec(select(ImportRun).order_by(ImportRun.id)).all()
        ok, report = run_all_checks(session)

    assert len(features) == 2
    assert len(raw_features) == 2
    assert runs[-1].status == "success"
    assert ok is True
    assert report["errors"] == []

    processed = import_features(engine=engine, base_url="https://example.com")
    assert processed == 2

    with Session(engine) as session:
        features = session.exec(select(Feature)).all()
        raw_features = session.exec(
            select(RawEntity).where(RawEntity.entity_type == "feature")
        ).all()
        run = session.exec(
            select(ImportRun).order_by(ImportRun.id.desc()).limit(1)
        ).one()

    assert len(features) == 2
    assert len(raw_features) == 2
    assert run.notes is not None
    notes = json.loads(run.notes)
    assert notes["raw_created"] == 0
    assert notes["raw_updated"] == 0
    assert notes["feature_created"] == 0
    assert notes["feature_updated"] == 0

    payloads["cunning-action"] = _payload("cunning-action", 3)
    _stub_client(monkeypatch, payloads)

    processed = import_features(engine=engine, base_url="https://example.com")
    assert processed == 2

    with Session(engine) as session:
        feature = session.exec(
            select(Feature).where(Feature.source_key == "cunning-action")
        ).one()
        run = session.exec(
            select(ImportRun).order_by(ImportRun.id.desc()).limit(1)
        ).one()

    assert feature.level == 3
    notes = json.loads(run.notes)
    assert notes["raw_created"] == 0
    assert notes["raw_updated"] == 1
    assert notes["feature_created"] == 0
    assert notes["feature_updated"] == 1
