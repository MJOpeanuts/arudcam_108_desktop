import json
from datetime import datetime, timezone

from sqlalchemy import Select, select
from sqlalchemy.orm import sessionmaker

from arducam_capture.domain.models.capture import CaptureFilters, CaptureResult, CaptureStatus
from arducam_capture.domain.models.camera import CameraDescriptor
from arducam_capture.infrastructure.persistence.orm.models import CameraRecord, CaptureRecord


class SqlAlchemyCaptureRepository:
    def __init__(self, sessions: sessionmaker) -> None:
        self._sessions = sessions

    def ensure_camera(self, descriptor: CameraDescriptor) -> None:
        now = datetime.now(timezone.utc)
        with self._sessions.begin() as session:
            record = session.get(CameraRecord, descriptor.camera_id)
            if record is None:
                session.add(
                    CameraRecord(
                        id=descriptor.camera_id,
                        device_key=descriptor.camera_id,
                        name=descriptor.name,
                        hardware_reference=descriptor.hardware_reference,
                        os_platform="unknown",
                        first_seen_at_utc=now,
                        last_seen_at_utc=now,
                        is_connected=descriptor.is_connected,
                        capabilities_json=None,
                    )
                )
            else:
                record.name = descriptor.name
                record.last_seen_at_utc = now
                record.is_connected = descriptor.is_connected

    def add(self, result: CaptureResult) -> None:
        with self._sessions.begin() as session:
            session.add(
                CaptureRecord(
                    id=result.capture_id,
                    camera_id=result.camera_id,
                    file_name=result.file_name,
                    relative_path=result.relative_path,
                    created_at_utc=result.created_at_utc,
                    width=result.width,
                    height=result.height,
                    image_format=result.image_format,
                    file_size_bytes=result.file_size_bytes,
                    created_at_local=result.created_at_local,
                    focus_value=result.controls.get("focus_absolute"),
                    exposure=result.controls.get("exposure_absolute"),
                    gain=result.controls.get("gain"),
                    white_balance=result.controls.get("white_balance"),
                    brightness=result.controls.get("brightness"),
                    extra_params_json=json.dumps(
                        {
                            key: value
                            for key, value in result.controls.items()
                            if key
                            not in {
                                "focus_absolute",
                                "exposure_absolute",
                                "gain",
                                "white_balance",
                                "brightness",
                            }
                        },
                        sort_keys=True,
                    ),
                    capture_duration_ms=result.duration_ms,
                    capture_mode=f"still_{result.width}x{result.height}",
                    sha256=result.sha256,
                    status=result.status.value,
                )
            )

    def list(self, filters: CaptureFilters = CaptureFilters()) -> list[CaptureRecord]:
        statement: Select[tuple[CaptureRecord]] = select(CaptureRecord)
        if filters.camera_id:
            statement = statement.where(CaptureRecord.camera_id == filters.camera_id)
        if filters.status:
            statement = statement.where(CaptureRecord.status == filters.status.value)
        if filters.start_utc:
            statement = statement.where(CaptureRecord.created_at_utc >= filters.start_utc)
        if filters.end_utc:
            statement = statement.where(CaptureRecord.created_at_utc <= filters.end_utc)
        statement = statement.order_by(CaptureRecord.created_at_utc.desc())
        with self._sessions() as session:
            return list(session.scalars(statement))

    def get(self, capture_id: str) -> CaptureRecord | None:
        with self._sessions() as session:
            return session.get(CaptureRecord, capture_id)

    def update_status(self, capture_id: str, status: CaptureStatus) -> None:
        with self._sessions.begin() as session:
            record = session.get(CaptureRecord, capture_id)
            if record is not None:
                record.status = status.value
