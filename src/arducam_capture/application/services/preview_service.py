from arducam_capture.application.ports.camera_adapter import CameraAdapter

PREVIEW_MAX_WIDTH = 1280


class PreviewService:
    """Fournit un aperçu basse résolution, distinct de la résolution de capture finale."""

    def __init__(self, camera: CameraAdapter) -> None:
        self._camera = camera

    def get_frame(self, camera_id: str, max_width: int = PREVIEW_MAX_WIDTH) -> bytes:
        if max_width < 1:
            raise ValueError("La largeur d'aperçu doit être positive.")
        return self._camera.capture_preview(camera_id, min(max_width, PREVIEW_MAX_WIDTH)).data
