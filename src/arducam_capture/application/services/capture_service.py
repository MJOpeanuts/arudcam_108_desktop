import hashlib
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from arducam_capture.application.ports.camera_adapter import CameraAdapter
from arducam_capture.domain.models.capture import CaptureResult
from arducam_capture.infrastructure.persistence.capture_repository import (
    SqlAlchemyCaptureRepository,
)
from arducam_capture.infrastructure.storage.local_file_storage import LocalFileStorage


class CaptureService:
    def __init__(
        self,
        camera: CameraAdapter,
        repository: SqlAlchemyCaptureRepository,
        storage: LocalFileStorage,
    ) -> None:
        self._camera = camera
        self._repository = repository
        self._storage = storage

    def capture(self, camera_id: str, width: int, height: int) -> CaptureResult:
        capture_id = str(uuid4())
        started = time.monotonic()
        image = self._camera.capture_still(camera_id, width, height)
        extension = image.source_format.lower()
        if extension not in {"png", "tif", "tiff", "jpg", "jpeg"}:
            raise ValueError(f"Format d'image non pris en charge : {image.source_format}.")
        relative_path, path = self._storage.write_capture(capture_id, image.data, extension)
        created = datetime.now(UTC)
        result = CaptureResult(
            capture_id=capture_id,
            camera_id=camera_id,
            file_name=Path(relative_path).name,
            relative_path=relative_path,
            created_at_utc=created,
            created_at_local=created.astimezone().isoformat(),
            width=image.width,
            height=image.height,
            image_format=extension,
            file_size_bytes=path.stat().st_size,
            sha256=hashlib.sha256(image.data).hexdigest(),
            controls=image.controls,
            duration_ms=round((time.monotonic() - started) * 1000),
            capture_mode=f"still_{image.width}x{image.height}",
        )
        try:
            self._repository.add(result)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return result
