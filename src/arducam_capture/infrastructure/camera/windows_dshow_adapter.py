"""Adaptateur Windows 11 (DirectShow via OpenCV) pour l'Arducam B0494C.

Aucune capacité n'est supposée : les modes YUY2 sont sondés (réglage puis relecture) et
seul le focus manuel (0–1023, datasheet B0494) est exposé. Exposition, gain, balance des
blancs et luminosité restent masqués tant qu'ils ne sont pas validés sur la caméra réelle.
"""

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from arducam_capture.application.ports.camera_adapter import CameraAdapter
from arducam_capture.domain.errors import (
    CameraDisconnectedError,
    CameraDiscoveryError,
    CameraNotFoundError,
    CapabilityNotSupportedError,
)
from arducam_capture.domain.models.camera import (
    CameraCapabilities,
    CameraDescriptor,
    ControlKind,
    ControlRange,
    RawStillImage,
)

# Modes annoncés par la datasheet ; ils sont sondés, jamais supposés disponibles.
CANDIDATE_MODES: tuple[tuple[int, int], ...] = (
    (1280, 720),
    (3840, 2160),
    (4000, 3000),
    (6000, 9000),
    (12000, 9000),
)
PREVIEW_MODE = (1280, 720)
FOCUS_RANGE = ControlRange(0, 1023, default=None)
WARMUP_FRAMES = 3
READ_RETRIES = 3


logger = logging.getLogger(__name__)


def list_directshow_devices() -> list[str]:
    """Liste les périphériques vidéo DirectShow.

    COM doit être initialisé dans le thread appelant (les threads Streamlit ne le sont pas).

    Hypothèse (à confirmer sur matériel) : l'ordre de ``FilterGraph().get_input_devices()``
    (CLSID_VideoInputDeviceCategory) est celui utilisé par ``cv2.VideoCapture(index,
    cv2.CAP_DSHOW)``, car OpenCV énumère la même catégorie DirectShow. L'index PyGrabber
    est donc utilisé comme index OpenCV.
    """
    import comtypes  # type: ignore[import-not-found]
    from pygrabber.dshow_graph import FilterGraph  # type: ignore[import-not-found]

    comtypes.CoInitialize()
    try:
        return list(FilterGraph().get_input_devices())
    finally:
        comtypes.CoUninitialize()


class WindowsDirectShowCameraAdapter(CameraAdapter):
    def __init__(
        self,
        name_pattern: str = "arducam",
        cv2_module: Any = None,
        device_lister: Callable[[], list[str]] = list_directshow_devices,
    ) -> None:
        if cv2_module is None:
            import cv2 as cv2_module
        self._cv2 = cv2_module
        self._pattern = name_pattern.lower()
        self._list_devices = device_lister
        self._lock = threading.RLock()
        self._devices: dict[str, int] = {}
        self._capabilities: dict[str, CameraCapabilities] = {}
        self._handle: Any = None
        self._handle_key: tuple[str, int, int] | None = None
        self._focus: dict[str, int] = {}

    # --- détection ---
    def discover(self) -> list[CameraDescriptor]:
        with self._lock:
            try:
                names = self._list_devices()
            except Exception as error:
                logger.exception("Échec de l'énumération des périphériques DirectShow")
                self._devices = {}
                self._release()
                raise CameraDiscoveryError(
                    "Impossible d'énumérer les caméras DirectShow "
                    f"({type(error).__name__}: {error}). Consultez les journaux."
                ) from error
            self._devices = {}
            found: list[CameraDescriptor] = []
            for index, name in enumerate(names):
                if self._pattern not in name.lower():
                    continue
                camera_id = f"dshow:{index}:{name}"
                self._devices[camera_id] = index
                found.append(
                    CameraDescriptor(camera_id=camera_id, name=name, hardware_reference=None)
                )
            if not found:
                self._release()
            return found

    def _index(self, camera_id: str) -> int:
        if camera_id not in self._devices:
            self.discover()
        try:
            return self._devices[camera_id]
        except KeyError as error:
            raise CameraNotFoundError(f"Caméra introuvable : {camera_id}.") from error

    # --- ouverture / fermeture ---
    def _release(self) -> None:
        if self._handle is not None:
            try:
                self._handle.release()
            finally:
                self._handle = None
                self._handle_key = None

    def close(self) -> None:
        with self._lock:
            self._release()

    def _open(self, camera_id: str, width: int, height: int) -> Any:
        index = self._index(camera_id)
        key = (camera_id, width, height)
        if self._handle is not None and self._handle_key == key:
            return self._handle
        self._release()
        cv2 = self._cv2
        handle = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not handle.isOpened():
            handle.release()
            raise CameraDisconnectedError(f"Impossible d'ouvrir la caméra {camera_id}.")
        handle.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"YUY2"))
        handle.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        handle.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._handle, self._handle_key = handle, key
        return handle

    def _actual_size(self, handle: Any) -> tuple[int, int]:
        cv2 = self._cv2
        return int(handle.get(cv2.CAP_PROP_FRAME_WIDTH)), int(handle.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # --- modes YUY2 ---
    def get_capabilities(self, camera_id: str) -> CameraCapabilities:
        with self._lock:
            cached = self._capabilities.get(camera_id)
            if cached is not None:
                return cached
            modes: list[tuple[int, int]] = []
            for width, height in CANDIDATE_MODES:
                self._release()
                handle = self._open(camera_id, width, height)
                if self._actual_size(handle) == (width, height):
                    modes.append((width, height))
            self._release()
            capabilities = CameraCapabilities(
                supported_resolutions=tuple(modes),
                supported_controls={ControlKind.FOCUS_ABSOLUTE: FOCUS_RANGE},
                supports_autofocus=False,
            )
            self._capabilities[camera_id] = capabilities
            return capabilities

    # --- images ---
    def _grab(self, handle: Any, camera_id: str, warmup: int) -> Any:
        frame = None
        for attempt in range(warmup + READ_RETRIES):
            ok, candidate = handle.read()
            if not ok or candidate is None:
                if attempt >= warmup:
                    time.sleep(0.2)
                if not handle.isOpened():
                    break
                continue
            frame = candidate
            if attempt >= warmup - 1:
                return frame
        self._release()
        self._capabilities.pop(camera_id, None)
        raise CameraDisconnectedError(f"La caméra {camera_id} ne fournit plus d'images.")

    def _encode_png(self, frame: Any, camera_id: str) -> bytes:
        cv2 = self._cv2
        ok, buffer = cv2.imencode(".png", frame, [cv2.IMWRITE_PNG_COMPRESSION, 1])
        if not ok:
            raise CameraDisconnectedError(f"Encodage de l'image impossible ({camera_id}).")
        return bytes(buffer.tobytes())

    def capture_still(self, camera_id: str, width: int, height: int) -> RawStillImage:
        with self._lock:
            if (width, height) not in self.get_capabilities(camera_id).supported_resolutions:
                raise CapabilityNotSupportedError(
                    f"Résolution {width}×{height} non confirmée par la caméra."
                )
            self._release()
            handle = self._open(camera_id, width, height)
            self._apply_focus(handle, camera_id)
            try:
                frame = self._grab(handle, camera_id, WARMUP_FRAMES)
                actual_height, actual_width = frame.shape[:2]
                data = self._encode_png(frame, camera_id)
            finally:
                self._release()
            controls: dict[str, int] = {}
            if camera_id in self._focus:
                controls[ControlKind.FOCUS_ABSOLUTE.value] = self._focus[camera_id]
            return RawStillImage(
                data=data,
                width=actual_width,
                height=actual_height,
                source_format="PNG",
                controls=controls,
            )

    def capture_preview(self, camera_id: str, max_width: int) -> RawStillImage:
        with self._lock:
            width, height = PREVIEW_MODE
            handle = self._open(camera_id, width, height)
            self._apply_focus(handle, camera_id)
            frame = self._grab(handle, camera_id, 1)
            actual_height, actual_width = frame.shape[:2]
            if actual_width > max_width:
                scale = max_width / actual_width
                frame = self._cv2.resize(frame, (max_width, round(actual_height * scale)))
                actual_height, actual_width = frame.shape[:2]
            return RawStillImage(
                data=self._encode_png(frame, camera_id),
                width=actual_width,
                height=actual_height,
                source_format="PNG",
                controls={},
            )

    # --- contrôles ---
    def _apply_focus(self, handle: Any, camera_id: str) -> None:
        if camera_id in self._focus:
            cv2 = self._cv2
            handle.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            handle.set(cv2.CAP_PROP_FOCUS, self._focus[camera_id])

    def set_control(self, camera_id: str, control: ControlKind, value: int) -> None:
        with self._lock:
            self._index(camera_id)
            if control is not ControlKind.FOCUS_ABSOLUTE:
                raise CapabilityNotSupportedError(f"Réglage non pris en charge : {control}.")
            FOCUS_RANGE.validate(value)
            self._focus[camera_id] = value
            if self._handle is not None and self._handle_key and self._handle_key[0] == camera_id:
                self._apply_focus(self._handle, camera_id)

    def get_control(self, camera_id: str, control: ControlKind) -> int | None:
        with self._lock:
            self._index(camera_id)
            if control is ControlKind.FOCUS_ABSOLUTE:
                return self._focus.get(camera_id)
            return None

    def set_autofocus(self, camera_id: str, enabled: bool) -> None:
        raise CapabilityNotSupportedError("L'autofocus n'est pas implémenté dans la v1.")
