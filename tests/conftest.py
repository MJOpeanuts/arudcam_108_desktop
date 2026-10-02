from pathlib import Path

import pytest

from arducam_capture.composition import create_services
from arducam_capture.platform.migrations import upgrade_database


@pytest.fixture
def services(tmp_path: Path):
    upgrade_database(tmp_path)
    return create_services(tmp_path)
