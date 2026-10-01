import pytest

from arducam_capture.domain.models.camera import ControlRange


def test_control_range_rejects_values_outside_supported_step() -> None:
    value_range = ControlRange(minimum=10, maximum=20, step=2)

    with pytest.raises(ValueError):
        value_range.validate(21)
    with pytest.raises(ValueError):
        value_range.validate(13)

    value_range.validate(14)

