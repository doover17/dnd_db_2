"""Command-line interface for dnd_db."""

from __future__ import annotations

import argparse

from sqlalchemy import inspect

from dnd_db.config import get_db_path
from dnd_db.db.engine import create_db_and_tables, get_engine


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="dnd_db CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Initialize the database schema")
    subparsers.add_parser("info", help="Show database path and table names")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init-db":
        _init_db()
    elif args.command == "info":
        _info()
    else:
        parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
