from __future__ import annotations

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from sqlmodel import Session, select

from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.ingest.api_client import SrdApiClient
from dnd_db.ingest.import_spells import import_spells
from dnd_db.models.spell import Spell
from dnd_db.verify.checks import run_all_checks


def _payload(index: str, level: int) -> dict:
    return {
        "index": index,
        "name": index.replace("-", " ").title(),
        "level": level,
        "school": {"index": "evocation", "name": "Evocation"},
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


def test_run_all_checks(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "verify.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    payloads = {
        "acid-arrow": _payload("acid-arrow", 2),
        "alarm": _payload("alarm", 1),
    }
    _stub_client(monkeypatch, payloads)
    import_spells(engine=engine, base_url="https://example.com")

    with Session(engine) as session:
        ok, report = run_all_checks(session)
    assert ok is True
    assert report["errors"] == []

    with Session(engine) as session:
        spell = Spell(
            source_id=1,
            raw_entity_id=None,
            source_key="missing-raw",
            name="Missing Raw",
            level=1,
            concentration=False,
            ritual=False,
        )
        session.add(spell)
        session.commit()

    with Session(engine) as session:
        ok, report = run_all_checks(session)

    assert ok is False
    assert any("missing raw_entity_id" in error for error in report["errors"])
