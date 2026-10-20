from pathlib import Path
import re
import tempfile

from django.conf import settings
from django.http import FileResponse
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell

from .backups import sqlite_snapshot
from .models import Selection


class PrivateDownload(FileResponse):
    def __init__(self, directory, path, filename, content_type):
        self.directory = directory
        try:
            super().__init__(path.open("rb"), as_attachment=True, filename=filename, content_type=content_type)
        except Exception:
            directory.cleanup()
            raise
        self["Cache-Control"] = "private, no-store"
        self["X-Content-Type-Options"] = "nosniff"

    def close(self):
        if self.closed:
            return
        try:
            super().close()
        finally:
            self.directory.cleanup()


def stamp():
    return timezone.localtime().strftime("%Y%m%d-%H%M%S")


def database_download():
    config = settings.DATABASES["default"]
    if config["ENGINE"] != "django.db.backends.sqlite3":
        raise ValueError("Este download está disponível somente para SQLite.")
    directory = tempfile.TemporaryDirectory(prefix="presentes-db-")
    path = Path(directory.name) / "snapshot.db"
    try:
        path.touch(mode=0o600)
        sqlite_snapshot(config["NAME"], path)
        return PrivateDownload(directory, path, f"banco-presentes-{stamp()}.db", "application/vnd.sqlite3")
    except Exception:
        directory.cleanup()
        raise


def text_cell(sheet, value):
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value))
    cell = WriteOnlyCell(sheet, value=value)
    cell.data_type = "s"  # Inclusive textos iniciados por =, +, -, @.
    return cell


def selections_download():
    directory = tempfile.TemporaryDirectory(prefix="presentes-xlsx-")
    path = Path(directory.name) / "conferencia.xlsx"
    workbook = Workbook(write_only=True)
    try:
        sheet = workbook.create_sheet("Conferência")
        sheet.column_dimensions["A"].width = 35
        sheet.column_dimensions["B"].width = 55
        sheet.append([text_cell(sheet, value) for value in ("Nome e primeiro sobrenome", "Presente selecionado")])
        for selection in Selection.objects.select_related("product").order_by("created_at", "pk").iterator():
            sheet.append([text_cell(sheet, selection.first_name + " " + selection.surname), text_cell(sheet, selection.product.name)])
        path.touch(mode=0o600)
        workbook.save(path)
        return PrivateDownload(directory, path, f"conferencia-presentes-{stamp()}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception:
        directory.cleanup()
        raise
    finally:
        workbook.close()
