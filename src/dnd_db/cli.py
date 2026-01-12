"""Command-line interface for dnd_db."""

from __future__ import annotations

import argparse

from sqlalchemy import inspect
from sqlmodel import Session, select

from dnd_db.config import get_db_path
from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.db.upsert import upsert_raw_entity
from dnd_db.models.source import Source


def _init_db() -> None:
    engine = get_engine()
    create_db_and_tables(engine)
    print(f"Database initialized at {get_db_path()}")


def _info() -> None:
    engine = get_engine()
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Database path: {get_db_path()}")
    print("Tables:")
    for table in tables:
        print(f"- {table}")


def _ensure_source(session: Session, name: str, base_url: str | None = None) -> Source:
    existing = session.exec(select(Source).where(Source.name == name)).one_or_none()
    if existing is not None:
        return existing
    source = Source(name=name, base_url=base_url)
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


def _seed_source() -> None:
    engine = get_engine()
    create_db_and_tables(engine)
    with Session(engine) as session:
        source = _ensure_source(session, "5e-bits", "https://www.5e-bits.com")
        print(f"Source id: {source.id}")


def _upsert_raw_sample() -> None:
    engine = get_engine()
    create_db_and_tables(engine)
    sample_payload = {
        "index": "acid-arrow",
        "name": "Acid Arrow",
        "level": 2,
        "school": {"index": "evocation", "name": "Evocation"},
        "srd": True,
        "url": "/api/spells/acid-arrow",
    }
    with Session(engine) as session:
        source = _ensure_source(session, "5e-bits", "https://www.5e-bits.com")
        entity, created, updated = upsert_raw_entity(
            session,
            source_id=source.id,
            entity_type="spell",
            source_key=sample_payload["index"],
            payload=sample_payload,
            name=sample_payload["name"],
            srd=sample_payload.get("srd"),
            url=sample_payload.get("url"),
        )
    if created:
        print(f"Created raw entity {entity.id}")
    elif updated:
        print(f"Updated raw entity {entity.id}")
    else:
        print(f"No change for raw entity {entity.id}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="dnd_db CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Initialize the database schema")
    subparsers.add_parser("info", help="Show database path and table names")
    subparsers.add_parser("seed-source", help="Seed the default source metadata")
    subparsers.add_parser(
        "upsert-raw-sample", help="Upsert a sample raw entity payload"
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init-db":
        _init_db()
    elif args.command == "info":
        _info()
    elif args.command == "seed-source":
        _seed_source()
    elif args.command == "upsert-raw-sample":
        _upsert_raw_sample()
    else:
        parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
