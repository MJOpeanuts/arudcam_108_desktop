import platform
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from arducam_capture.application.ports.camera_adapter import CameraAdapter


@dataclass(frozen=True)
class DiagnosticReport:
    python_version: str
    os_name: str
    camera_count: int
    camera_names: tuple[str, ...]
    data_dir: str
    database_path: str
    database_exists: bool
    free_disk_bytes: int
    log_files: tuple[str, ...]


class DiagnosticService:
    def __init__(self, camera: CameraAdapter, data_dir: Path) -> None:
        self._camera = camera
        self._data_dir = data_dir

    def build_report(self) -> DiagnosticReport:
        cameras = self._camera.discover()
        database = self._data_dir / "database" / "arducam_capture.db"
        logs = self._data_dir / "logs"
        return DiagnosticReport(
            python_version=sys.version.split()[0],
            os_name=platform.platform(),
            camera_count=len(cameras),
            camera_names=tuple(camera.name for camera in cameras),
            data_dir=str(self._data_dir),
            database_path=str(database),
            database_exists=database.is_file(),
            free_disk_bytes=shutil.disk_usage(self._data_dir).free,
            log_files=tuple(sorted(p.name for p in logs.glob("*.log"))) if logs.is_dir() else (),
        )
