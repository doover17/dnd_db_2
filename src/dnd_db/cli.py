"""Command-line interface for dnd_db."""

from __future__ import annotations

import argparse
import json

from sqlalchemy import delete, inspect
from sqlmodel import Session, select

from dnd_db.config import get_api_base_url, get_db_path
from dnd_db.db.engine import create_db_and_tables, get_engine
from dnd_db.db.upsert import upsert_raw_entity
from dnd_db.ingest.api_client import SrdApiClient
from dnd_db.ingest.import_classes import import_classes
from dnd_db.ingest.import_features import import_features
from dnd_db.ingest.import_spells import import_spells
from dnd_db.ingest.import_subclasses import import_subclasses
from dnd_db.ingest.load_choices import load_choices
from dnd_db.ingest.load_relationships import load_relationships
from dnd_db.models.import_run import ImportRun
from dnd_db.models.relationships import (
    ClassFeatureLink,
    SpellClassLink,
    SubclassFeatureLink,
)
from dnd_db.models.source import Source
from dnd_db.verify.checks import run_all_checks
from dnd_db.verify.choices import verify_choices


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


def _import_spells(
    base_url: str | None, refresh: bool, limit: int | None
) -> None:
    engine = get_engine()
    create_db_and_tables(engine)
    processed = import_spells(
        engine=engine, base_url=base_url, limit=limit, refresh=refresh
    )

    with Session(engine) as session:
        run = session.exec(
            select(ImportRun).order_by(ImportRun.id.desc()).limit(1)
        ).one_or_none()

    print(f"Database path: {get_db_path()}")
    print(f"Processed spells: {processed}")
    if run is None:
        return
    print(f"Import status: {run.status}")
    if run.notes:
        try:
            notes = json.loads(run.notes)
        except json.JSONDecodeError:
            notes = None
        if isinstance(notes, dict):
            raw_created = notes.get("raw_created", 0)
            raw_updated = notes.get("raw_updated", 0)
            spell_created = notes.get("spell_created", 0)
            spell_updated = notes.get("spell_updated", 0)
            print(
                "Raw entities created/updated: "
                f"{raw_created}/{raw_updated}"
            )
            print(
                "Spells created/updated: "
                f"{spell_created}/{spell_updated}"
            )


def _import_classes(
    base_url: str | None, refresh: bool, limit: int | None
) -> None:
    engine = get_engine()
    create_db_and_tables(engine)
    processed = import_classes(
        engine=engine, base_url=base_url, limit=limit, refresh=refresh
    )

    with Session(engine) as session:
        run = session.exec(
            select(ImportRun).order_by(ImportRun.id.desc()).limit(1)
        ).one_or_none()

    print(f"Database path: {get_db_path()}")
    print(f"Processed classes: {processed}")
    if run is None:
        return
    print(f"Import status: {run.status}")
    if run.notes:
        try:
            notes = json.loads(run.notes)
        except json.JSONDecodeError:
            notes = None
        if isinstance(notes, dict):
            raw_created = notes.get("raw_created", 0)
            raw_updated = notes.get("raw_updated", 0)
            class_created = notes.get("class_created", 0)
            class_updated = notes.get("class_updated", 0)
            print(
                "Raw entities created/updated: "
                f"{raw_created}/{raw_updated}"
            )
            print(
                "Classes created/updated: "
                f"{class_created}/{class_updated}"
            )


def _import_subclasses(
    base_url: str | None, refresh: bool, limit: int | None
) -> None:
    engine = get_engine()
    create_db_and_tables(engine)
    processed = import_subclasses(
        engine=engine, base_url=base_url, limit=limit, refresh=refresh
    )

    with Session(engine) as session:
        run = session.exec(
            select(ImportRun).order_by(ImportRun.id.desc()).limit(1)
        ).one_or_none()

    print(f"Database path: {get_db_path()}")
    print(f"Processed subclasses: {processed}")
    if run is None:
        return
    print(f"Import status: {run.status}")
    if run.notes:
        try:
            notes = json.loads(run.notes)
        except json.JSONDecodeError:
            notes = None
        if isinstance(notes, dict):
            raw_created = notes.get("raw_created", 0)
            raw_updated = notes.get("raw_updated", 0)
            subclass_created = notes.get("subclass_created", 0)
            subclass_updated = notes.get("subclass_updated", 0)
            print(
                "Raw entities created/updated: "
                f"{raw_created}/{raw_updated}"
            )
            print(
                "Subclasses created/updated: "
                f"{subclass_created}/{subclass_updated}"
            )


def _import_features(
    base_url: str | None, refresh: bool, limit: int | None
) -> None:
    engine = get_engine()
    create_db_and_tables(engine)
    processed = import_features(
        engine=engine, base_url=base_url, limit=limit, refresh=refresh
    )

    with Session(engine) as session:
        run = session.exec(
            select(ImportRun).order_by(ImportRun.id.desc()).limit(1)
        ).one_or_none()

    print(f"Database path: {get_db_path()}")
    print(f"Processed features: {processed}")
    if run is None:
        return
    print(f"Import status: {run.status}")
    if run.notes:
        try:
            notes = json.loads(run.notes)
        except json.JSONDecodeError:
            notes = None
        if isinstance(notes, dict):
            raw_created = notes.get("raw_created", 0)
            raw_updated = notes.get("raw_updated", 0)
            feature_created = notes.get("feature_created", 0)
            feature_updated = notes.get("feature_updated", 0)
            print(
                "Raw entities created/updated: "
                f"{raw_created}/{raw_updated}"
            )
            print(
                "Features created/updated: "
                f"{feature_created}/{feature_updated}"
            )



def _verify() -> None:
    engine = get_engine()
    create_db_and_tables(engine)
    with Session(engine) as session:
        ok, report = run_all_checks(session)

    counts = report["counts"]
    print("Counts:")
    print(f"- sources: {counts['sources']}")
    print(f"- import_runs: {counts['import_runs']}")
    print(f"- raw_entities: {counts['raw_entities']}")
    print(f"- raw_entities_spell: {counts['raw_entities_spell']}")
    print(f"- raw_entities_class: {counts['raw_entities_class']}")
    print(f"- raw_entities_subclass: {counts['raw_entities_subclass']}")
    print(f"- raw_entities_feature: {counts['raw_entities_feature']}")
    print(f"- spells: {counts['spells']}")
    print(f"- classes: {counts['classes']}")
    print(f"- subclasses: {counts['subclasses']}")
    print(f"- features: {counts['features']}")
    print(f"- class_features: {counts['class_features']}")
    print(f"- subclass_features: {counts['subclass_features']}")
    print(f"- spell_classes: {counts['spell_classes']}")

    warnings = report.get("warnings", [])
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")

    errors = report.get("errors", [])
    if errors:
        print("Errors:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("No errors detected.")


def _load_relationships(source_name: str) -> None:
    engine = get_engine()
    create_db_and_tables(engine)
    summary = load_relationships(engine=engine, source_name=source_name)
    print(f"Database path: {get_db_path()}")
    print("Relationships loaded:")
    print(f"- class_features_created: {summary['class_features_created']}")
    print(f"- subclass_features_created: {summary['subclass_features_created']}")
    print(f"- spell_classes_created: {summary['spell_classes_created']}")
    print(f"- missing_refs_count: {summary['missing_refs_count']}")


def _load_choices(source_name: str) -> None:
    engine = get_engine()
    create_db_and_tables(engine)
    summary = load_choices(engine=engine, source_name=source_name)
    print(f"Database path: {get_db_path()}")
    print("Choices loaded:")
    print(f"- choice_groups_created: {summary['choice_groups_created']}")
    print(f"- choice_options_created: {summary['choice_options_created']}")
    print(f"- missing_owner_count: {summary['missing_owner_count']}")
    print(f"- missing_option_refs_count: {summary['missing_option_refs_count']}")


def _verify_choices() -> None:
    engine = get_engine()
    create_db_and_tables(engine)
    with Session(engine) as session:
        report = verify_choices(session)
    errors = report.get("errors", [])
    if errors:
        print("Choice verification errors:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("No choice verification errors detected.")


def _rebuild_relationships(source_name: str, truncate: bool) -> None:
    engine = get_engine()
    create_db_and_tables(engine)
    if truncate:
        with Session(engine) as session:
            source = session.exec(
                select(Source).where(Source.name == source_name)
            ).one_or_none()
            if source is None:
                raise ValueError("Run importers first: source not found.")
            session.exec(
                delete(ClassFeatureLink).where(ClassFeatureLink.source_id == source.id)
            )
            session.exec(
                delete(SubclassFeatureLink).where(
                    SubclassFeatureLink.source_id == source.id
                )
            )
            session.exec(
                delete(SpellClassLink).where(SpellClassLink.source_id == source.id)
            )
            session.commit()
            print(f"Truncated relationships for source {source.name} ({source.id}).")
    _load_relationships(source_name)


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

    import_spells_parser = subparsers.add_parser(
        "import-spells", help="Import spells from the SRD API"
    )
    import_spells_parser.add_argument(
        "--limit", type=int, default=None, help="Limit number of spells"
    )
    import_spells_parser.add_argument(
        "--base-url",
        default=get_api_base_url(),
        help="Override API base URL",
    )
    import_spells_parser.add_argument("--refresh", action="store_true")

    import_classes_parser = subparsers.add_parser(
        "import-classes", help="Import classes from the SRD API"
    )
    import_classes_parser.add_argument(
        "--limit", type=int, default=None, help="Limit number of classes"
    )
    import_classes_parser.add_argument(
        "--base-url",
        default=get_api_base_url(),
        help="Override API base URL",
    )
    import_classes_parser.add_argument("--refresh", action="store_true")

    import_subclasses_parser = subparsers.add_parser(
        "import-subclasses", help="Import subclasses from the SRD API"
    )
    import_subclasses_parser.add_argument(
        "--limit", type=int, default=None, help="Limit number of subclasses"
    )
    import_subclasses_parser.add_argument(
        "--base-url",
        default=get_api_base_url(),
        help="Override API base URL",
    )
    import_subclasses_parser.add_argument("--refresh", action="store_true")

    import_features_parser = subparsers.add_parser(
        "import-features", help="Import features from the SRD API"
    )
    import_features_parser.add_argument(
        "--limit", type=int, default=None, help="Limit number of features"
    )
    import_features_parser.add_argument(
        "--base-url",
        default=get_api_base_url(),
        help="Override API base URL",
    )
    import_features_parser.add_argument("--refresh", action="store_true")

    subparsers.add_parser("verify", help="Run verification checks")

    load_relationships_parser = subparsers.add_parser(
        "load-relationships", help="Load relationship join tables"
    )
    load_relationships_parser.add_argument(
        "--source-name",
        default="5e-bits",
        help="Source name to load relationships for",
    )

    rebuild_relationships_parser = subparsers.add_parser(
        "rebuild-relationships", help="Rebuild relationship join tables"
    )
    rebuild_relationships_parser.add_argument(
        "--source-name",
        default="5e-bits",
        help="Source name to load relationships for",
    )
    rebuild_relationships_parser.add_argument(
        "--truncate",
        action="store_true",
        help="Delete existing relationships for the source before loading",
    )

    load_choices_parser = subparsers.add_parser(
        "load-choices", help="Load choice groups and options"
    )
    load_choices_parser.add_argument(
        "--source-name",
        default="5e-bits",
        help="Source name to load choices for",
    )

    subparsers.add_parser(
        "verify-choices", help="Verify choice group and option integrity"
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
    elif args.command == "api-index":
        _api_index(args.resource, args.base_url, args.refresh)
    elif args.command == "api-get":
        _api_get(args.resource, args.index, args.base_url, args.refresh)
    elif args.command == "api-fetch-all":
        _api_fetch_all(args.resource, args.base_url, args.refresh, args.limit)
    elif args.command == "import-spells":
        _import_spells(args.base_url, args.refresh, args.limit)
    elif args.command == "import-classes":
        _import_classes(args.base_url, args.refresh, args.limit)
    elif args.command == "import-subclasses":
        _import_subclasses(args.base_url, args.refresh, args.limit)
    elif args.command == "import-features":
        _import_features(args.base_url, args.refresh, args.limit)
    elif args.command == "verify":
        _verify()
    elif args.command == "load-relationships":
        _load_relationships(args.source_name)
    elif args.command == "rebuild-relationships":
        _rebuild_relationships(args.source_name, args.truncate)
    elif args.command == "load-choices":
        _load_choices(args.source_name)
    elif args.command == "verify-choices":
        _verify_choices()
    else:
        parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
