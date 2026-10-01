import csv
from io import BytesIO, StringIO

from openpyxl import Workbook

from arudcam_capture.domain.models.capture import CaptureFilters
from arudcam_capture.infrastructure.persistence.capture_repository import (
    SqlAlchemyCaptureRepository,
)

EXPORT_COLUMNS = (
    "id",
    "camera_id",
    "file_name",
    "relative_path",
    "created_at_utc",
    "width",
    "height",
    "image_format",
    "file_size_bytes",
    "sha256",
    "status",
)


def _safe_cell(value: object) -> object:
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


class ExportService:
    def __init__(self, repository: SqlAlchemyCaptureRepository) -> None:
        self._repository = repository

    def export_csv(self, filters: CaptureFilters = CaptureFilters(), delimiter: str = ",") -> bytes:
        if len(delimiter) != 1:
            raise ValueError("Le séparateur CSV doit être un seul caractère.")
        output = StringIO(newline="")
        writer = csv.writer(output, delimiter=delimiter)
        writer.writerow(EXPORT_COLUMNS)
        for record in self._repository.list(filters):
            row = [_safe_cell(getattr(record, column)) for column in EXPORT_COLUMNS]
            writer.writerow(row)
        return output.getvalue().encode("utf-8-sig")

    def export_excel(self, filters: CaptureFilters = CaptureFilters()) -> bytes:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Captures"
        sheet.append(EXPORT_COLUMNS)
        for record in self._repository.list(filters):
            sheet.append([_safe_cell(getattr(record, column)) for column in EXPORT_COLUMNS])
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()

