import pytest

from arducam_capture.domain.models.camera import ControlRange


def test_control_range_rejects_values_outside_supported_step() -> None:
    value_range = ControlRange(minimum=10, maximum=20, step=2)

    with pytest.raises(ValueError):
        value_range.validate(21)
    with pytest.raises(ValueError):
        value_range.validate(13)

    value_range.validate(14)


def test_data_dir_default_windows_path(monkeypatch, tmp_path) -> None:
    from arducam_capture.platform.config import AppSettings

    monkeypatch.delenv("ARDUCAM_CAPTURE_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert AppSettings().resolved_data_dir() == tmp_path / "DataPeanuts" / "ArducamCapture"


def test_preview_and_diagnostic(services, tmp_path) -> None:
    camera = services.discovery.list_available_cameras()[0]
    assert services.preview.get_frame(camera.camera_id).startswith(b"\x89PNG")
    report = services.diagnostic.build_report()
    assert report.database_exists and report.camera_count == 1
    for name in ("captures", "exports", "logs", "backups", "config", "temp"):
        assert (tmp_path / name).is_dir()
