from io import BytesIO

from PIL import Image

from arducam_capture.application.ports.camera_adapter import CameraAdapter
from arducam_capture.domain.errors import CameraNotFoundError, CapabilityNotSupportedError
from arducam_capture.domain.models.camera import (
    CameraCapabilities,
    CameraDescriptor,
    ControlKind,
    ControlRange,
    RawStillImage,
)


class FakeCameraAdapter(CameraAdapter):
    """Deterministic camera used for local development until hardware is validated."""

    camera = CameraDescriptor(
        camera_id="fake-arducam",
        name="Caméra de démonstration (simulée)",
        hardware_reference="simulation",
    )
    _controls = {
        ControlKind.FOCUS_ABSOLUTE: ControlRange(0, 1023, default=512),
        ControlKind.BRIGHTNESS: ControlRange(0, 255, default=128),
    }

    def __init__(self) -> None:
        self._values = {key: control.default or 0 for key, control in self._controls.items()}

    def discover(self) -> list[CameraDescriptor]:
        return [self.camera]

    def get_capabilities(self, camera_id: str) -> CameraCapabilities:
        self._check_camera(camera_id)
        return CameraCapabilities(
            supported_resolutions=((640, 480), (1280, 720)),
            supported_controls=self._controls.copy(),
        )

    def capture_still(self, camera_id: str, width: int, height: int) -> RawStillImage:
        self._check_camera(camera_id)
        if (width, height) not in self.get_capabilities(camera_id).supported_resolutions:
            raise CapabilityNotSupportedError("Résolution non prise en charge par la caméra simulée.")
        image = Image.new("RGB", (width, height), color=(35, 89, 135))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return RawStillImage(
            data=buffer.getvalue(),
            width=width,
            height=height,
            source_format="PNG",
            controls=self._values.copy(),
        )

    def set_control(self, camera_id: str, control: ControlKind, value: int) -> None:
        self._check_camera(camera_id)
        try:
            supported = self._controls[control]
        except KeyError as error:
            raise CapabilityNotSupportedError(f"Réglage non pris en charge : {control}.") from error
        supported.validate(value)
        self._values[control] = value

    def get_control(self, camera_id: str, control: ControlKind) -> int | None:
        self._check_camera(camera_id)
        return self._values.get(control)

    def set_autofocus(self, camera_id: str, enabled: bool) -> None:
        self._check_camera(camera_id)
        raise NotImplementedError("L'autofocus n'est pas implémenté dans la v1.")

    @classmethod
    def _check_camera(cls, camera_id: str) -> None:
        if camera_id != cls.camera.camera_id:
            raise CameraNotFoundError(f"Caméra introuvable : {camera_id}.")

