import hashlib
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import load_workbook

from arducam_capture.application.services.capture_service import CaptureService
from arducam_capture.domain.models.camera import RawStillImage
from arducam_capture.domain.models.capture import CaptureStatus
from arducam_capture.infrastructure.camera.fake_camera_adapter import FakeCameraAdapter
from arducam_capture.infrastructure.persistence.capture_repository import (
    SqlAlchemyCaptureRepository,
)
from arducam_capture.infrastructure.persistence.orm import Base
from arducam_capture.infrastructure.persistence.session import (
    create_database_engine,
    create_session_factory,
)
from arducam_capture.infrastructure.storage.local_file_storage import LocalFileStorage


def test_capture_writes_one_file_with_checksum_and_database_row(services, tmp_path: Path) -> None:
    camera = services.discovery.list_available_cameras()[0]
    result = services.capture.capture(camera.camera_id, 640, 480)

    saved_file = tmp_path / result.relative_path
    rows = services.repository.list()
    assert saved_file.is_file()
    assert result.sha256 == hashlib.sha256(saved_file.read_bytes()).hexdigest()
    assert len(rows) == 1
    assert rows[0].status == CaptureStatus.CAPTURED.value
    assert rows[0].file_size_bytes == saved_file.stat().st_size


def test_history_marks_missing_file_and_requires_delete_confirmation(
    services, tmp_path: Path
) -> None:
    camera = services.discovery.list_available_cameras()[0]
    result = services.capture.capture(camera.camera_id, 640, 480)
    (tmp_path / result.relative_path).unlink()

    assert services.history.list_captures()[0].status == CaptureStatus.MISSING.value
    with pytest.raises(ValueError):
        services.history.delete_capture(result.capture_id, confirmed=False)


def test_confirmed_delete_removes_image_and_marks_capture_deleted(services, tmp_path: Path) -> None:
    camera = services.discovery.list_available_cameras()[0]
    result = services.capture.capture(camera.camera_id, 640, 480)

    services.history.delete_capture(result.capture_id, confirmed=True)

    assert not (tmp_path / result.relative_path).exists()
    assert services.repository.get(result.capture_id).status == CaptureStatus.DELETED.value


def test_export_has_bom_and_neutralizes_spreadsheet_formulas(services) -> None:
    camera = services.discovery.list_available_cameras()[0]
    result = services.capture.capture(camera.camera_id, 640, 480)
    row = services.repository.get(result.capture_id)
    assert row is not None
    with services.repository._sessions.begin() as session:
        saved = session.get(type(row), result.capture_id)
        assert saved is not None
        saved.file_name = " =1+1"

    output = services.export.export_csv()
    assert output.startswith(b"\xef\xbb\xbf")
    assert b"' =1+1" in output
    excel = services.export.export_excel()
    assert excel.startswith(b"PK")
    workbook = load_workbook(BytesIO(excel))
    assert workbook.active["C2"].data_type == "s"
    assert workbook.active["C2"].value == "' =1+1"


def test_invalid_image_format_never_writes_a_file(tmp_path: Path) -> None:
    class InvalidCamera(FakeCameraAdapter):
        def capture_still(self, camera_id: str, width: int, height: int) -> RawStillImage:
            self._check_camera(camera_id)
            return RawStillImage(b"data", width, height, "../evil", {})

    data_dir = tmp_path / "data"
    engine = create_database_engine(data_dir / "database.db")
    Base.metadata.create_all(engine)
    sessions = create_session_factory(engine)
    repository = SqlAlchemyCaptureRepository(sessions)
    camera = InvalidCamera()
    descriptor = camera.discover()[0]
    repository.ensure_camera(descriptor)
    service = CaptureService(camera, repository, LocalFileStorage(data_dir))

    with pytest.raises(ValueError, match="Format d'image non pris en charge"):
        service.capture(descriptor.camera_id, 640, 480)
    assert not (data_dir / "captures").exists()
