from dataclasses import dataclass
from enum import StrEnum


class ControlKind(StrEnum):
    FOCUS_ABSOLUTE = "focus_absolute"
    EXPOSURE_ABSOLUTE = "exposure_absolute"
    GAIN = "gain"
    WHITE_BALANCE = "white_balance"
    BRIGHTNESS = "brightness"


@dataclass(frozen=True)
class ControlRange:
    minimum: int
    maximum: int
    step: int = 1
    default: int | None = None

    def __post_init__(self) -> None:
        if self.minimum > self.maximum or self.step < 1:
            raise ValueError("Plage de contrôle invalide.")
        if self.default is not None and not self.minimum <= self.default <= self.maximum:
            raise ValueError("La valeur par défaut doit appartenir à la plage.")

    def validate(self, value: int) -> None:
        if not self.minimum <= value <= self.maximum:
            raise ValueError(
                f"La valeur doit être comprise entre {self.minimum} et {self.maximum}."
            )
        if (value - self.minimum) % self.step:
            raise ValueError(f"La valeur doit respecter un incrément de {self.step}.")


@dataclass(frozen=True)
class CameraCapabilities:
    supported_resolutions: tuple[tuple[int, int], ...]
    supported_controls: dict[ControlKind, ControlRange]
    supports_autofocus: bool = False


@dataclass(frozen=True)
class CameraDescriptor:
    camera_id: str
    name: str
    hardware_reference: str | None = None
    is_connected: bool = True


@dataclass(frozen=True)
class RawStillImage:
    data: bytes
    width: int
    height: int
    source_format: str
    controls: dict[str, int]
