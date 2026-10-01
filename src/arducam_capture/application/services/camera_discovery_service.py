from arducam_capture.application.ports.camera_adapter import CameraAdapter
from arducam_capture.domain.models.camera import CameraDescriptor


class CameraDiscoveryService:
    def __init__(self, camera: CameraAdapter) -> None:
        self._camera = camera

    def list_available_cameras(self) -> list[CameraDescriptor]:
        return self._camera.discover()
