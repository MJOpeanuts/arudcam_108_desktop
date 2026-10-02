from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from arducam_capture.domain.models.capture import CaptureStatus
from arducam_capture.infrastructure.persistence.orm.base import Base


class CameraRecord(Base):
    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    device_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    hardware_reference: Mapped[str | None] = mapped_column(String)
    os_platform: Mapped[str] = mapped_column(String, nullable=False)
    first_seen_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_connected: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    capabilities_json: Mapped[str | None] = mapped_column(Text)


class CaptureRecord(Base):
    __tablename__ = "captures"
    __table_args__ = (
        CheckConstraint(
            "status IN ('captured', 'missing', 'deleted', 'failed')",
            name="ck_captures_status",
        ),
        Index("ix_captures_created_at_utc", "created_at_utc"),
        Index("ix_captures_camera_id", "camera_id"),
        Index("ix_captures_status", "status"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    camera_id: Mapped[str] = mapped_column(
        ForeignKey("cameras.id", ondelete="RESTRICT"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    relative_path: Mapped[str] = mapped_column(String, nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at_local: Mapped[str] = mapped_column(String, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    image_format: Mapped[str] = mapped_column(String, nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    focus_value: Mapped[int | None] = mapped_column(Integer)
    exposure: Mapped[int | None] = mapped_column(Integer)
    gain: Mapped[int | None] = mapped_column(Integer)
    white_balance: Mapped[int | None] = mapped_column(Integer)
    brightness: Mapped[int | None] = mapped_column(Integer)
    extra_params_json: Mapped[str | None] = mapped_column(Text)
    capture_mode: Mapped[str] = mapped_column(String, nullable=False)
    capture_duration_ms: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)

    @property
    def status_value(self) -> CaptureStatus:
        return CaptureStatus(self.status)


class SettingRecord(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)
    updated_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
