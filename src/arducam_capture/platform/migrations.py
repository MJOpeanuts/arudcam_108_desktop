import os
import sqlite3
import sys
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import URL

INITIAL_REVISION = "0001_initial_schema"
INITIAL_TABLES = frozenset({"cameras", "captures", "settings"})
LOCK_TIMEOUT_SECONDS = 120.0


class DatabaseInconsistentError(RuntimeError):
    """Base SQLite partiellement initialisée ou incohérente."""


class MigrationLock:
    """Verrou interprocessus bloquant dédié aux migrations."""

    def __init__(self, path: Path, timeout: float = LOCK_TIMEOUT_SECONDS) -> None:
        self._path = path
        self._timeout = timeout
        self._handle = None

    def __enter__(self) -> "MigrationLock":
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self._path.open("a+b")
        deadline = time.monotonic() + self._timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if time.monotonic() >= deadline:
                    self._handle.close()
                    self._handle = None
                    raise TimeoutError(
                        "Impossible d'obtenir le verrou de migration de la base de données."
                    ) from None
                time.sleep(0.05)

    def __exit__(self, *_exc: object) -> None:
        if self._handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None


def _check_database_state(database: Path) -> None:
    """Refuse une base dont le schéma et alembic_version sont incohérents."""
    if not database.exists():
        return
    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        version = None
        if "alembic_version" in tables:
            row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
            version = row[0] if row else None
    present = INITIAL_TABLES & tables
    if version is None and present:
        problem = "tables applicatives présentes sans révision Alembic : " + ", ".join(
            sorted(present)
        )
    elif version == INITIAL_REVISION and not INITIAL_TABLES <= tables:
        problem = "tables manquantes : " + ", ".join(sorted(INITIAL_TABLES - tables))
    else:
        return
    raise DatabaseInconsistentError(
        f"Base de données partiellement initialisée ({database}) : {problem}. "
        "La migration n'a pas été exécutée afin de ne pas masquer l'incohérence. "
        "Restaurez une sauvegarde de la base (ou supprimez ce fichier après l'avoir "
        "copié ailleurs si elle ne contient aucune donnée à conserver), puis relancez."
    )


def upgrade_database(data_dir: Path) -> None:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).parents[3]))
    config = Config(str(root / "alembic.ini"))
    database = data_dir / "database" / "arducam_capture.db"
    database.parent.mkdir(parents=True, exist_ok=True)
    url = URL.create("sqlite", database=str(database)).render_as_string(hide_password=False)
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    with MigrationLock(data_dir / "database" / "migrations.lock"):
        _check_database_state(database)
        command.upgrade(config, "head")
