from arducam_capture.application.ports.camera_adapter import CameraAdapter
from arducam_capture.domain.errors import CapabilityNotSupportedError
from arducam_capture.domain.models.camera import CameraCapabilities, ControlKind


class CameraControlService:
    def __init__(self, camera: CameraAdapter) -> None:
        self._camera = camera

    def get_capabilities(self, camera_id: str) -> CameraCapabilities:
        return self._camera.get_capabilities(camera_id)

    def get_control(self, camera_id: str, control: ControlKind) -> int | None:
        return self._camera.get_control(camera_id, control)

    def set_control(self, camera_id: str, control: ControlKind, value: int) -> None:
        capabilities = self._camera.get_capabilities(camera_id)
        control_range = capabilities.supported_controls.get(control)
        if control_range is None:
            raise CapabilityNotSupportedError(f"Réglage non pris en charge : {control}.")
        control_range.validate(value)
        self._camera.set_control(camera_id, control, value)

    def set_autofocus(self, camera_id: str, enabled: bool) -> None:
        self._camera.set_autofocus(camera_id, enabled)
