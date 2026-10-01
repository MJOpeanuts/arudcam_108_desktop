from abc import ABC, abstractmethod

from arducam_capture.domain.models.camera import (
    CameraCapabilities,
    CameraDescriptor,
    ControlKind,
    RawStillImage,
)


class CameraAdapter(ABC):
    @abstractmethod
    def discover(self) -> list[CameraDescriptor]: ...

    @abstractmethod
    def get_capabilities(self, camera_id: str) -> CameraCapabilities: ...

    @abstractmethod
    def capture_still(self, camera_id: str, width: int, height: int) -> RawStillImage: ...

    @abstractmethod
    def set_control(self, camera_id: str, control: ControlKind, value: int) -> None: ...

    @abstractmethod
    def get_control(self, camera_id: str, control: ControlKind) -> int | None: ...

    @abstractmethod
    def set_autofocus(self, camera_id: str, enabled: bool) -> None: ...
