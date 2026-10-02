from dataclasses import dataclass
from pathlib import Path

from arducam_capture.application.services.camera_control_service import CameraControlService
from arducam_capture.application.services.camera_discovery_service import (
    CameraDiscoveryService,
)
from arducam_capture.application.services.capture_history_service import CaptureHistoryService
from arducam_capture.application.services.capture_service import CaptureService
from arducam_capture.application.services.diagnostic_service import DiagnosticService
from arducam_capture.application.services.export_service import ExportService
from arducam_capture.application.services.preview_service import PreviewService
from arducam_capture.infrastructure.camera.fake_camera_adapter import FakeCameraAdapter
from arducam_capture.infrastructure.persistence.capture_repository import (
    SqlAlchemyCaptureRepository,
)
from arducam_capture.infrastructure.persistence.session import (
    create_database_engine,
    create_session_factory,
)
from arducam_capture.infrastructure.storage.local_file_storage import LocalFileStorage
from arducam_capture.platform.config import AppSettings
from arducam_capture.platform.migrations import upgrade_database


@dataclass
class ApplicationServices:
    discovery: CameraDiscoveryService
    control: CameraControlService
    capture: CaptureService
    history: CaptureHistoryService
    export: ExportService
    repository: SqlAlchemyCaptureRepository
    preview: PreviewService
    diagnostic: DiagnosticService


def create_services(data_dir: Path) -> ApplicationServices:
    data_dir.mkdir(parents=True, exist_ok=True)
    AppSettings.ensure_layout(data_dir)
    upgrade_database(data_dir)
    engine = create_database_engine(data_dir / "database" / "arducam_capture.db")
    sessions = create_session_factory(engine)
    camera = FakeCameraAdapter()
    repository = SqlAlchemyCaptureRepository(sessions)
    repository.ensure_camera(camera.discover()[0])
    storage = LocalFileStorage(data_dir)
    return ApplicationServices(
        discovery=CameraDiscoveryService(camera),
        control=CameraControlService(camera),
        capture=CaptureService(camera, repository, storage),
        history=CaptureHistoryService(repository, storage),
        export=ExportService(repository),
        repository=repository,
        preview=PreviewService(camera),
        diagnostic=DiagnosticService(camera, data_dir),
    )
