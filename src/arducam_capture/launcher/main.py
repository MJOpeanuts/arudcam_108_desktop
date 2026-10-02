import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

from arducam_capture.platform.config import AppSettings
from arducam_capture.platform.instance_lock import InstanceLock
from arducam_capture.platform.migrations import DatabaseInconsistentError, upgrade_database

HOST = "127.0.0.1"
PORT = 8501
URL = f"http://{HOST}:{PORT}"


def _open_browser_when_ready(timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((HOST, PORT), timeout=1):
                break
        except OSError:
            time.sleep(0.3)
    else:
        return
    webbrowser.open(URL)


def main() -> None:
    if getattr(sys, "frozen", False):
        # Application fenêtrée (sans console) : stdout/stderr peuvent être None.
        if sys.stdout is None:
            sys.stdout = open(os.devnull, "w")  # noqa: SIM115
        if sys.stderr is None:
            sys.stderr = open(os.devnull, "w")  # noqa: SIM115
    data_dir = AppSettings().resolved_data_dir()
    try:
        lock = InstanceLock(data_dir / "arducam-capture.lock")
        lock.__enter__()
    except RuntimeError:
        # Déjà lancée : on rouvre simplement l'interface existante.
        webbrowser.open(URL)
        return
    with lock:
        # Migrations terminées avant le démarrage de Streamlit et du navigateur.
        AppSettings.ensure_layout(data_dir)
        try:
            upgrade_database(data_dir)
        except DatabaseInconsistentError as error:
            print(error, file=sys.stderr)
            raise SystemExit(1) from None
        threading.Thread(target=_open_browser_when_ready, daemon=True).start()
        from streamlit.web import cli

        if getattr(sys, "frozen", False):
            root = Path(sys.__dict__["_MEIPASS"])
            app = root / "arducam_capture" / "frontends" / "streamlit_app" / "app.py"
        else:
            app = Path(__file__).parents[1] / "frontends" / "streamlit_app" / "app.py"
        sys.argv = [
            "streamlit",
            "run",
            str(app),
            f"--server.address={HOST}",
            f"--server.port={PORT}",
            "--server.headless=true",
            "--global.developmentMode=false",
            "--browser.gatherUsageStats=false",
        ]
        cli.main()


if __name__ == "__main__":
    main()
