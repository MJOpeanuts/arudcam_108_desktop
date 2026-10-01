import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import URL


def upgrade_database(data_dir: Path) -> None:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).parents[3]))
    config = Config(str(root / "alembic.ini"))
    database = data_dir / "database" / "arducam_capture.db"
    database.parent.mkdir(parents=True, exist_ok=True)
    url = URL.create("sqlite", database=str(database)).render_as_string(hide_password=False)
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
