from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class CaptureStatus(StrEnum):
    CAPTURED = "captured"
    MISSING = "missing"
    DELETED = "deleted"
    FAILED = "failed"


@dataclass(frozen=True)
class CaptureResult:
    capture_id: str
    camera_id: str
    file_name: str
    relative_path: str
    created_at_utc: datetime
    width: int
    height: int
    image_format: str
    file_size_bytes: int
    sha256: str
    controls: dict[str, int]
    duration_ms: int
    status: CaptureStatus = CaptureStatus.CAPTURED


@dataclass(frozen=True)
class CaptureFilters:
    camera_id: str | None = None
    status: CaptureStatus | None = None
    start_utc: datetime | None = None
    end_utc: datetime | None = None

