class CameraNotFoundError(Exception):
    """Raised when the requested camera is unavailable."""


class CapabilityNotSupportedError(Exception):
    """Raised when a camera does not expose the requested capability."""


class CaptureStorageError(Exception):
    """Raised when a captured image cannot be stored safely."""


class CameraDisconnectedError(Exception):
    """Raised when the camera is unplugged or stops delivering frames."""
