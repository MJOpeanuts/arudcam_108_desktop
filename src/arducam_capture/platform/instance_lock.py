import os
from pathlib import Path
from types import TracebackType


class InstanceLock:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._handle = None

    def __enter__(self) -> "InstanceLock":
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self._path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, ImportError):
            self._handle.close()
            self._handle = None
            raise RuntimeError("Arducam Capture est déjà en cours d'exécution.") from None
        return self

    def __exit__(
        self,
        _exception_type: type[BaseException] | None,
        _exception: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        if self._handle is None:
            return
        if os.name == "nt":
            import msvcrt

            self._handle.seek(0)
            msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close()
