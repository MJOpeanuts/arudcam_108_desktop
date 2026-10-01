import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from arducam_capture.domain.errors import CaptureStorageError


class LocalFileStorage:
    def __init__(self, data_dir: Path) -> None:
        self.root = data_dir.resolve()
        self.capture_root = self.root / "captures"

    def write_capture(self, capture_id: str, image: bytes, extension: str) -> tuple[str, Path]:
        now = datetime.now(timezone.utc)
        directory = self.capture_root / now.strftime("%Y/%m/%d")
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{capture_id}.{extension}"
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=directory, prefix=".capture-", delete=False) as handle:
                temporary_path = Path(handle.name)
                handle.write(image)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, target)
        except OSError as error:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise CaptureStorageError("Impossible d'enregistrer l'image capturée.") from error
        return target.relative_to(self.root).as_posix(), target

    def resolve(self, relative_path: str) -> Path:
        target = (self.root / relative_path).resolve()
        if not target.is_relative_to(self.capture_root):
            raise CaptureStorageError("Chemin de capture en dehors du répertoire autorisé.")
        return target

