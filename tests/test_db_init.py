from __future__ import annotations

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import text

from dnd_db.db.engine import create_db_and_tables, get_engine


def test_db_init_creates_sqlite_file(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    engine = get_engine(str(db_path))

    create_db_and_tables(engine)

    assert db_path.exists()

    with engine.connect() as connection:
        result = connection.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='importrun'"
            )
        )
        assert result.first() is not None
