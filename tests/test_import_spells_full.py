from __future__ import annotations

from pathlib import Path
import sys

from sqlalchemy import func
from sqlmodel import Session, select

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

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
        "components": ["V", "S"],
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


def _duplicate_raw_spells(session: Session) -> list[tuple[int, str, int]]:
    return session.exec(
        select(
            RawEntity.source_id,
            RawEntity.source_key,
            func.count().label("count"),
        )
        .where(RawEntity.entity_type == "spell")
        .group_by(RawEntity.source_id, RawEntity.source_key)
        .having(func.count() > 1)
    ).all()


def _duplicate_spells(session: Session) -> list[tuple[int, str, int]]:
    return session.exec(
        select(
            Spell.source_id,
            Spell.source_key,
            func.count().label("count"),
        )
        .group_by(Spell.source_id, Spell.source_key)
        .having(func.count() > 1)
    ).all()


def test_import_spells_full_smoke(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "spells_full.db"
    engine = get_engine(str(db_path))
    create_db_and_tables(engine)

    payloads = {
        f"spell-{idx}": _payload(f"spell-{idx}", (idx % 9))
        for idx in range(1, 61)
    }
    _stub_client(monkeypatch, payloads)

    processed = import_spells(engine=engine, base_url="https://example.com")
    assert processed == len(payloads)

    with Session(engine) as session:
        spell_count = session.exec(select(func.count()).select_from(Spell)).one()
        raw_count = session.exec(
            select(func.count())
            .select_from(RawEntity)
            .where(RawEntity.entity_type == "spell")
        ).one()
        run = session.exec(
            select(ImportRun).order_by(ImportRun.id.desc()).limit(1)
        ).one()

        assert spell_count == raw_count == len(payloads)
        assert run.status == "success"
        assert _duplicate_raw_spells(session) == []
        assert _duplicate_spells(session) == []

    processed = import_spells(engine=engine, base_url="https://example.com")
    assert processed == len(payloads)

    with Session(engine) as session:
        spell_count = session.exec(select(func.count()).select_from(Spell)).one()
        raw_count = session.exec(
            select(func.count())
            .select_from(RawEntity)
            .where(RawEntity.entity_type == "spell")
        ).one()
        run = session.exec(
            select(ImportRun).order_by(ImportRun.id.desc()).limit(1)
        ).one()

        assert spell_count == raw_count == len(payloads)
        assert run.status == "success"
        assert _duplicate_raw_spells(session) == []
        assert _duplicate_spells(session) == []
