import multiprocessing
import sqlite3

import pytest
from sqlalchemy import inspect

from arducam_capture.infrastructure.persistence.session import create_database_engine
from arducam_capture.platform.migrations import DatabaseInconsistentError, upgrade_database


def test_upgrade_creates_initial_schema(tmp_path) -> None:
    upgrade_database(tmp_path)
    engine = create_database_engine(tmp_path / "database" / "arducam_capture.db")

    inspector = inspect(engine)
    assert {"cameras", "captures", "settings"} <= set(inspector.get_table_names())
    assert {index["name"] for index in inspector.get_indexes("captures")} >= {
        "ix_captures_camera_id",
        "ix_captures_created_at_utc",
        "ix_captures_status",
    }


def _version(tmp_path) -> list[str]:
    with sqlite3.connect(tmp_path / "database" / "arducam_capture.db") as connection:
        return [row[0] for row in connection.execute("SELECT version_num FROM alembic_version")]


def _init(data_dir) -> None:
    upgrade_database(data_dir)


def test_concurrent_initializations_and_data_preserved(tmp_path) -> None:
    ctx = multiprocessing.get_context("spawn")
    processes = [ctx.Process(target=_init, args=(tmp_path,)) for _ in range(2)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(120)
    assert [process.exitcode for process in processes] == [0, 0]
    assert _version(tmp_path) == ["0001_initial_schema"]

    database = tmp_path / "database" / "arducam_capture.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO settings (key, value, updated_at_utc) VALUES ('k', 'v', '2026-01-01')"
        )
    upgrade_database(tmp_path)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM settings WHERE key='k'").fetchall() == [("v",)]


def test_partial_database_raises_clear_error(tmp_path) -> None:
    database = tmp_path / "database" / "arducam_capture.db"
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE cameras (id TEXT)")
    with pytest.raises(DatabaseInconsistentError, match="Restaurez"):
        upgrade_database(tmp_path)
