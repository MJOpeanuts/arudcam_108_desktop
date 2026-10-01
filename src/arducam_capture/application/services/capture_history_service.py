from arudcam_capture.domain.errors import CaptureStorageError
from arudcam_capture.domain.models.capture import CaptureFilters, CaptureStatus
from arudcam_capture.infrastructure.persistence.capture_repository import (
    SqlAlchemyCaptureRepository,
)
from arudcam_capture.infrastructure.storage.local_file_storage import LocalFileStorage


class CaptureHistoryService:
    def __init__(
        self, repository: SqlAlchemyCaptureRepository, storage: LocalFileStorage
    ) -> None:
        self._repository = repository
        self._storage = storage

    def list_captures(self, filters: CaptureFilters = CaptureFilters()):
        records = self._repository.list(filters)
        for record in records:
            if record.status == CaptureStatus.CAPTURED.value:
                path = self._storage.resolve(record.relative_path)
                if not path.is_file():
                    self._repository.update_status(record.id, CaptureStatus.MISSING)
                    record.status = CaptureStatus.MISSING.value
        return records

    def delete_capture(self, capture_id: str, confirmed: bool) -> None:
        if not confirmed:
            raise ValueError("La suppression doit être explicitement confirmée.")
        record = self._repository.get(capture_id)
        if record is None:
            raise KeyError(f"Cliché introuvable : {capture_id}.")
        path = self._storage.resolve(record.relative_path)
        try:
            path.unlink(missing_ok=True)
        except OSError as error:
            raise CaptureStorageError("Impossible de supprimer le fichier du cliché.") from error
        self._repository.update_status(capture_id, CaptureStatus.DELETED)

