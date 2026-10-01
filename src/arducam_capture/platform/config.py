import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARDUCAM_CAPTURE_", extra="ignore")

    data_dir: Path | None = None

    def resolved_data_dir(self) -> Path:
        if self.data_dir is not None:
            return self.data_dir.expanduser().resolve()
        if home := os.environ.get("LOCALAPPDATA"):
            return Path(home) / "ArducamCapture"
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
        return base / "arducam-capture"
