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
            return Path(home) / "DataPeanuts" / "ArducamCapture"
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
        return base / "arducam-capture"

    @staticmethod
    def ensure_layout(data_dir: Path) -> None:
        for name in ("database", "captures", "exports", "logs", "backups", "config", "temp"):
            (data_dir / name).mkdir(parents=True, exist_ok=True)
