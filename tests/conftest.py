from pathlib import Path

import pytest

from arducam_capture.composition import create_services


@pytest.fixture
def services(tmp_path: Path):
    return create_services(tmp_path)

