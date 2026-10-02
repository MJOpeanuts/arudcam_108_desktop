import pytest

from arducam_capture.domain.errors import CameraDisconnectedError, CapabilityNotSupportedError
from arducam_capture.domain.models.camera import ControlKind
from arducam_capture.infrastructure.camera.windows_dshow_adapter import (
    WindowsDirectShowCameraAdapter,
)


class Frame:
    def __init__(self, width: int, height: int) -> None:
        self.shape = (height, width, 3)

    def tobytes(self) -> bytes:
        return b"\x89PNG-fake"


SUPPORTED = {(1280, 720), (3840, 2160), (4000, 3000), (12000, 9000)}


class FakeCv2:
    CAP_DSHOW = 700
    CAP_PROP_FOURCC = 6
    CAP_PROP_FRAME_WIDTH = 3
    CAP_PROP_FRAME_HEIGHT = 4
    CAP_PROP_FOCUS = 28
    CAP_PROP_AUTOFOCUS = 39
    IMWRITE_PNG_COMPRESSION = 16

    def __init__(self) -> None:
        self.connected = True
        self.sets: list[tuple[int, float]] = []
        cv2 = self

        class Handle:
            def __init__(self, index: int, backend: int) -> None:
                self.size = (640, 480)
                self.open = cv2.connected

            def isOpened(self) -> bool:  # noqa: N802
                return self.open and cv2.connected

            def set(self, prop: int, value: float) -> bool:
                cv2.sets.append((prop, value))
                if prop == cv2.CAP_PROP_FRAME_WIDTH:
                    self.size = (int(value), self.size[1])
                if prop == cv2.CAP_PROP_FRAME_HEIGHT:
                    h = int(value)
                    self.size = (self.size[0], h) if (self.size[0], h) in SUPPORTED else (640, 480)
                return True

            def get(self, prop: int) -> float:
                return float(self.size[0] if prop == cv2.CAP_PROP_FRAME_WIDTH else self.size[1])

            def read(self):
                if not cv2.connected:
                    return False, None
                return True, Frame(self.size[0] // 100, self.size[1] // 100)

            def release(self) -> None:
                self.open = False

        self.VideoCapture = Handle

    @staticmethod
    def VideoWriter_fourcc(*chars: str) -> int:  # noqa: N802
        return sum(ord(c) << (8 * i) for i, c in enumerate(chars))

    @staticmethod
    def imencode(ext: str, frame, params):
        return True, frame

    @staticmethod
    def resize(frame, size):
        return Frame(size[0], size[1])


@pytest.fixture
def cv2():
    return FakeCv2()


@pytest.fixture
def adapter(cv2):
    return WindowsDirectShowCameraAdapter(
        cv2_module=cv2, device_lister=lambda: ["Integrated Webcam", "Arducam 108MP USB Camera"]
    )


def test_discovers_only_matching_device(adapter) -> None:
    cameras = adapter.discover()
    assert [c.name for c in cameras] == ["Arducam 108MP USB Camera"]
    assert cameras[0].hardware_reference is None


def test_enumerates_only_confirmed_modes(adapter) -> None:
    camera = adapter.discover()[0]
    caps = adapter.get_capabilities(camera.camera_id)
    assert set(caps.supported_resolutions) == SUPPORTED
    assert set(caps.supported_controls) == {ControlKind.FOCUS_ABSOLUTE}
    assert not caps.supports_autofocus


def test_focus_bounds_and_application(adapter, cv2) -> None:
    camera = adapter.discover()[0]
    adapter.set_control(camera.camera_id, ControlKind.FOCUS_ABSOLUTE, 416)
    with pytest.raises(ValueError):
        adapter.set_control(camera.camera_id, ControlKind.FOCUS_ABSOLUTE, 1024)
    with pytest.raises(CapabilityNotSupportedError):
        adapter.set_control(camera.camera_id, ControlKind.GAIN, 1)
    image = adapter.capture_still(camera.camera_id, 12000, 9000)
    assert image.controls == {"focus_absolute": 416}
    assert (cv2.CAP_PROP_FOCUS, 416) in cv2.sets
    assert (cv2.CAP_PROP_AUTOFOCUS, 0) in cv2.sets


def test_unconfirmed_resolution_rejected(adapter) -> None:
    camera = adapter.discover()[0]
    with pytest.raises(CapabilityNotSupportedError):
        adapter.capture_still(camera.camera_id, 6000, 9000)


def test_disconnect_raises_and_recovers(adapter, cv2) -> None:
    camera = adapter.discover()[0]
    adapter.get_capabilities(camera.camera_id)
    cv2.connected = False
    with pytest.raises(CameraDisconnectedError):
        adapter.capture_still(camera.camera_id, 1280, 720)
    cv2.connected = True
    assert adapter.capture_still(camera.camera_id, 1280, 720).data.startswith(b"\x89PNG")
    assert adapter.capture_preview(camera.camera_id, 640).width <= 640


ARDUCAM = "Arducam B0494 (USB3 108MP)"


def test_two_devices_selects_only_arducam(cv2) -> None:
    adapter = WindowsDirectShowCameraAdapter(
        cv2_module=cv2, device_lister=lambda: ["Laptop Camera", ARDUCAM]
    )
    cameras = adapter.discover()
    assert [(c.camera_id, c.name) for c in cameras] == [(f"dshow:1:{ARDUCAM}", ARDUCAM)]


def test_name_filter_is_case_insensitive(cv2) -> None:
    adapter = WindowsDirectShowCameraAdapter(
        cv2_module=cv2, device_lister=lambda: ["Laptop Camera", "ARDUCAM b0494"]
    )
    assert [c.name for c in adapter.discover()] == ["ARDUCAM b0494"]


def test_discover_from_secondary_thread(cv2) -> None:
    import threading

    adapter = WindowsDirectShowCameraAdapter(
        cv2_module=cv2, device_lister=lambda: ["Laptop Camera", ARDUCAM]
    )
    result: list = []
    errors: list = []

    def run() -> None:
        try:
            result.extend(adapter.discover())
        except Exception as error:  # pragma: no cover
            errors.append(error)

    thread = threading.Thread(target=run)
    thread.start()
    thread.join()
    assert not errors
    assert [c.name for c in result] == [ARDUCAM]


def test_list_directshow_devices_initialises_com(monkeypatch) -> None:
    import sys
    import types

    calls: list[str] = []
    comtypes = types.ModuleType("comtypes")
    comtypes.CoInitialize = lambda: calls.append("init")  # type: ignore[attr-defined]
    comtypes.CoUninitialize = lambda: calls.append("uninit")  # type: ignore[attr-defined]

    class FilterGraph:
        def get_input_devices(self) -> list[str]:
            calls.append("list")
            return ["Laptop Camera", ARDUCAM]

    graph = types.ModuleType("pygrabber.dshow_graph")
    graph.FilterGraph = FilterGraph  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "comtypes", comtypes)
    monkeypatch.setitem(sys.modules, "pygrabber", types.ModuleType("pygrabber"))
    monkeypatch.setitem(sys.modules, "pygrabber.dshow_graph", graph)
    from arducam_capture.infrastructure.camera.windows_dshow_adapter import (
        list_directshow_devices,
    )

    assert list_directshow_devices() == ["Laptop Camera", ARDUCAM]
    assert calls == ["init", "list", "uninit"]


def test_discovery_failure_is_logged_and_distinct(cv2, caplog, monkeypatch) -> None:
    from arducam_capture.domain.errors import CameraDiscoveryError
    from arducam_capture.infrastructure.camera import windows_dshow_adapter

    # Une autre suite (alembic fileConfig) peut désactiver les loggers existants.
    monkeypatch.setattr(windows_dshow_adapter.logger, "disabled", False)

    def boom() -> list[str]:
        raise OSError("CoInitialize has not been called")

    adapter = WindowsDirectShowCameraAdapter(cv2_module=cv2, device_lister=boom)
    with caplog.at_level("ERROR"), pytest.raises(CameraDiscoveryError):
        adapter.discover()
    assert any(r.exc_info for r in caplog.records)
