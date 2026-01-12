"""Command-line interface for dnd_db."""

from __future__ import annotations

import argparse

from sqlalchemy import inspect
from sqlmodel import Session, select

from dnd_db.config import get_api_base_url, get_db_path
from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.db.upsert import upsert_raw_entity
from dnd_db.ingest.api_client import SrdApiClient
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


def _api_index(resource: str, base_url: str | None, refresh: bool) -> None:
    client = SrdApiClient(base_url=base_url, refresh=refresh)
    results = client.list_resources(resource)
    print(f"Resource '{resource}' count: {len(results)}")
    for entry in results[:5]:
        name = entry.get("name")
        index = entry.get("index")
        url = entry.get("url")
        print(f"- {name} ({index}) {url}")


def _api_get(resource: str, index: str, base_url: str | None, refresh: bool) -> None:
    client = SrdApiClient(base_url=base_url, refresh=refresh)
    payload = client.get_resource(resource, index)
    name = payload.get("name")
    url = payload.get("url")
    keys = ", ".join(sorted(payload.keys()))
    print(f"{name} ({payload.get('index')}) {url}")
    print(f"Keys: {keys}")


def _api_fetch_all(
    resource: str, base_url: str | None, refresh: bool, limit: int | None
) -> None:
    client = SrdApiClient(base_url=base_url, refresh=refresh)
    entries = client.list_resources(resource)
    if limit is not None:
        entries = entries[:limit]
    total = len(entries)
    for idx, entry in enumerate(entries, start=1):
        index = entry.get("index")
        if not index:
            print(f"Skipping entry without index: {entry}")
            continue
        client.get_resource(resource, index)
        if idx % 25 == 0 or idx == total:
            print(f"Fetched {idx}/{total} {resource}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="dnd_db CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Initialize the database schema")
    subparsers.add_parser("info", help="Show database path and table names")
    subparsers.add_parser("seed-source", help="Seed the default source metadata")
    subparsers.add_parser(
        "upsert-raw-sample", help="Upsert a sample raw entity payload"
    )

    api_index = subparsers.add_parser("api-index", help="List API resources")
    api_index.add_argument("resource")
    api_index.add_argument(
        "--base-url",
        default=get_api_base_url(),
        help="Override API base URL",
    )
    api_index.add_argument("--refresh", action="store_true", help="Bypass cache")

    api_get = subparsers.add_parser("api-get", help="Get a resource by index")
    api_get.add_argument("resource")
    api_get.add_argument("index")
    api_get.add_argument(
        "--base-url",
        default=get_api_base_url(),
        help="Override API base URL",
    )
    api_get.add_argument("--refresh", action="store_true", help="Bypass cache")

    api_fetch_all = subparsers.add_parser(
        "api-fetch-all", help="Fetch all resources for a type"
    )
    api_fetch_all.add_argument("resource")
    api_fetch_all.add_argument(
        "--limit", type=int, default=None, help="Limit number of records"
    )
    api_fetch_all.add_argument(
        "--base-url",
        default=get_api_base_url(),
        help="Override API base URL",
    )
    api_fetch_all.add_argument("--refresh", action="store_true", help="Bypass cache")
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
    elif args.command == "api-index":
        _api_index(args.resource, args.base_url, args.refresh)
    elif args.command == "api-get":
        _api_get(args.resource, args.index, args.base_url, args.refresh)
    elif args.command == "api-fetch-all":
        _api_fetch_all(args.resource, args.base_url, args.refresh, args.limit)
    else:
        parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
