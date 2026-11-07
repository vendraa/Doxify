"""Menjalankan konversi di thread terpisah supaya jendela tidak membeku (FR-32)."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QObject, Signal, Slot

from app.converters import CancelToken, ConversionSettings, DoxifyError, ImageConverter


class ConversionWorker(QObject):
    progress = Signal(int, int, str)  # langkah, total, keterangan
    finished = Signal(object)  # ConversionResult
    failed = Signal(str)  # pesan kesalahan yang aman ditampilkan

    def __init__(self, paths: Sequence[Path], output: Path, settings: ConversionSettings) -> None:
        super().__init__()
        self._paths = list(paths)
        self._output = Path(output)
        self._settings = settings
        self.cancel_token = CancelToken()

    def cancel(self) -> None:
        self.cancel_token.cancel()

    @Slot()
    def run(self) -> None:
        try:
            result = ImageConverter().convert(
                self._paths,
                self._output,
                self._settings,
                progress=self.progress.emit,
                cancel=self.cancel_token,
            )
        except DoxifyError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            # Pesan sengaja generik: tidak membocorkan nama file/path dari traceback.
            self.failed.emit(f"Terjadi kesalahan tak terduga ({exc.__class__.__name__}).")
        else:
            self.finished.emit(result)
