import sys
from pathlib import Path

from arducam_capture.platform.config import AppSettings
from arducam_capture.platform.instance_lock import InstanceLock


def main() -> None:
    data_dir = AppSettings().resolved_data_dir()
    with InstanceLock(data_dir / "arducam-capture.lock"):
        from streamlit.web import cli

        if getattr(sys, "frozen", False):
            root = Path(getattr(sys, "_MEIPASS"))
            app = root / "arducam_capture" / "frontends" / "streamlit_app" / "app.py"
        else:
            app = Path(__file__).parents[1] / "frontends" / "streamlit_app" / "app.py"
        sys.argv = [
            "streamlit",
            "run",
            str(app),
            "--server.address=127.0.0.1",
            "--server.headless=true",
            "--browser.gatherUsageStats=false",
        ]
        cli.main()


if __name__ == "__main__":
    main()
