from sqlalchemy import inspect

from arducam_capture.infrastructure.persistence.session import create_database_engine
from arducam_capture.platform.migrations import upgrade_database


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
