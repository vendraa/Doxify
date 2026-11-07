"""Jendela utama Doxify."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QThread, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QSlider, QVBoxLayout, QWidget, QCheckBox,
)

from app.converters import ConversionResult
from app.ui.file_list import FileListWidget
from app.ui.logic import (
    FileListState, format_size, summarize_rejections, summarize_result, suggest_output_name,
)
from app.ui.worker import ConversionWorker
from app.utils.settings_store import (
    MAX_JPEG_QUALITY, MIN_UI_JPEG_QUALITY, SettingsStore, UserSettings,
)

IMAGE_FILTER = "Gambar (*.jpg *.jpeg *.png)"

MODE_CHOICES = [("Gabungkan jadi satu PDF", "merged"), ("Satu PDF per gambar", "separate")]
PAGE_CHOICES = [("A4", "a4"), ("Letter", "letter"), ("Ukuran asli gambar", "original")]
ORIENTATION_CHOICES = [("Otomatis (ikuti gambar)", "auto"), ("Potret", "portrait"), ("Lanskap", "landscape")]
MARGIN_CHOICES = [("Tanpa margin", "none"), ("Kecil (10 mm)", "small"), ("Sedang (20 mm)", "medium")]
QUALITY_CHOICES = [("Asli (tanpa kompres ulang)", "original"), ("Terkompres (file lebih kecil)", "compressed")]

_ICONS = {
    "success": QMessageBox.Icon.Information,
    "warning": QMessageBox.Icon.Warning,
    "error": QMessageBox.Icon.Critical,
    "cancelled": QMessageBox.Icon.Information,
}


def reveal_in_file_manager(path: Path) -> None:
    """Buka folder hasil dan sorot file-nya (FR-43)."""
    if sys.platform == "win32":
        subprocess.Popen(["explorer", f"/select,{path}"])  # explorer selalu keluar dengan kode 1; abaikan
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))


def _make_combo(choices: list[tuple[str, str]]) -> QComboBox:
    combo = QComboBox()
    for label, value in choices:
        combo.addItem(label, value)
    return combo


def _set_combo(combo: QComboBox, value: str) -> None:
    index = combo.findData(value)
    if index >= 0:
        combo.setCurrentIndex(index)


class MainWindow(QMainWindow):
    conversion_finished = Signal(object)  # ConversionResult; juga dipakai tes smoke

    def __init__(self, store: SettingsStore | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Doxify")
        self.resize(980, 640)
        self.setMinimumSize(780, 500)

        self.state = FileListState()
        self.store = store or SettingsStore()
        self.user_settings = self.store.load()
        self._busy = False
        self.last_error: str | None = None
        self._thread: QThread | None = None
        self._worker: ConversionWorker | None = None

        self._build_ui()
        self._apply_settings_to_widgets(self.user_settings)
        self._connect_signals()
        self._render_list()

    # ---- membangun UI -----------------------------------------------------

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)

        body = QHBoxLayout()
        outer.addLayout(body, 1)

        # kiri: daftar file
        left = QVBoxLayout()
        body.addLayout(left, 1)
        self.list_widget = FileListWidget()
        left.addWidget(self.list_widget, 1)
        self.count_label = QLabel()
        left.addWidget(self.count_label)

        buttons = QHBoxLayout()
        left.addLayout(buttons)
        self.btn_add = QPushButton("Tambah File...")
        self.btn_remove = QPushButton("Hapus Terpilih")
        self.btn_clear = QPushButton("Kosongkan")
        self.btn_up = QPushButton("Naik")
        self.btn_down = QPushButton("Turun")
        for b in (self.btn_add, self.btn_remove, self.btn_clear):
            buttons.addWidget(b)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_up)
        buttons.addWidget(self.btn_down)

        # kanan: pengaturan
        self.settings_box = QGroupBox("Pengaturan")
        self.settings_box.setFixedWidth(300)
        body.addWidget(self.settings_box)
        form = QFormLayout(self.settings_box)
        self.combo_mode = _make_combo(MODE_CHOICES)
        self.combo_page = _make_combo(PAGE_CHOICES)
        self.combo_orientation = _make_combo(ORIENTATION_CHOICES)
        self.combo_margin = _make_combo(MARGIN_CHOICES)
        self.combo_quality = _make_combo(QUALITY_CHOICES)
        self.slider_quality = QSlider(Qt.Orientation.Horizontal)
        self.slider_quality.setRange(MIN_UI_JPEG_QUALITY, MAX_JPEG_QUALITY)
        self.quality_label = QLabel()
        self.chk_strip = QCheckBox("Hapus metadata (lokasi GPS, tipe kamera)")
        self.chk_strip.setToolTip("Metadata EXIF dihapus tanpa mengubah kualitas gambar.")
        form.addRow("Output", self.combo_mode)
        form.addRow("Ukuran halaman", self.combo_page)
        form.addRow("Orientasi", self.combo_orientation)
        form.addRow("Margin", self.combo_margin)
        form.addRow("Kualitas", self.combo_quality)
        form.addRow(self.quality_label, self.slider_quality)
        form.addRow(self.chk_strip)

        # bawah: aksi + progress
        actions = QHBoxLayout()
        outer.addLayout(actions)
        self.status_label = QLabel("Siap. Seret gambar ke jendela ini untuk memulai.")
        actions.addWidget(self.status_label, 1)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(220)
        self.progress.setVisible(False)
        actions.addWidget(self.progress)
        self.btn_cancel = QPushButton("Batal")
        self.btn_cancel.setVisible(False)
        actions.addWidget(self.btn_cancel)
        self.btn_convert = QPushButton("Konversi")
        self.btn_convert.setDefault(True)
        self.btn_convert.setMinimumWidth(120)
        actions.addWidget(self.btn_convert)

    def _connect_signals(self) -> None:
        self.btn_add.clicked.connect(self.on_add_clicked)
        self.btn_remove.clicked.connect(self.on_remove_clicked)
        self.btn_clear.clicked.connect(self.on_clear_clicked)
        self.btn_up.clicked.connect(self.on_move_up)
        self.btn_down.clicked.connect(self.on_move_down)
        self.btn_convert.clicked.connect(self.on_convert_clicked)
        self.btn_cancel.clicked.connect(self.on_cancel_clicked)

        self.list_widget.itemSelectionChanged.connect(self._refresh_buttons)
        # Antrean (queued) agar dialog tidak muncul di tengah penanganan drop.
        self.list_widget.filesDropped.connect(self.add_paths, Qt.ConnectionType.QueuedConnection)
        self.list_widget.moveRequested.connect(self.on_move_requested, Qt.ConnectionType.QueuedConnection)

        self.combo_page.currentIndexChanged.connect(self._refresh_setting_states)
        self.combo_quality.currentIndexChanged.connect(self._refresh_setting_states)
        self.slider_quality.valueChanged.connect(self._refresh_setting_states)

        delete = QShortcut(QKeySequence(QKeySequence.StandardKey.Delete), self.list_widget)
        delete.setContext(Qt.ShortcutContext.WidgetShortcut)
        delete.activated.connect(self.on_remove_clicked)
        open_files = QShortcut(QKeySequence(QKeySequence.StandardKey.Open), self)
        open_files.activated.connect(self.on_add_clicked)

    # ---- pengaturan -------------------------------------------------------

    def _apply_settings_to_widgets(self, s: UserSettings) -> None:
        _set_combo(self.combo_mode, s.output_mode)
        _set_combo(self.combo_page, s.page_size)
        _set_combo(self.combo_orientation, s.orientation)
        _set_combo(self.combo_margin, s.margin)
        _set_combo(self.combo_quality, s.quality)
        self.slider_quality.setValue(s.jpeg_quality)
        self.chk_strip.setChecked(s.strip_metadata)
        self._refresh_setting_states()

    def read_settings(self) -> UserSettings:
        return UserSettings(
            output_mode=str(self.combo_mode.currentData()),
            page_size=str(self.combo_page.currentData()),
            orientation=str(self.combo_orientation.currentData()),
            margin=str(self.combo_margin.currentData()),
            quality=str(self.combo_quality.currentData()),
            jpeg_quality=self.slider_quality.value(),
            strip_metadata=self.chk_strip.isChecked(),
            last_output_dir=self.user_settings.last_output_dir,
        )

    def _refresh_setting_states(self) -> None:
        original_size = self.combo_page.currentData() == "original"
        self.combo_orientation.setEnabled(not original_size and not self._busy)
        self.combo_orientation.setToolTip(
            "Tidak berlaku pada ukuran asli: halaman mengikuti ukuran gambar." if original_size else ""
        )
        compressed = self.combo_quality.currentData() == "compressed"
        self.slider_quality.setEnabled(compressed and not self._busy)
        self.quality_label.setText(f"Kualitas JPEG: {self.slider_quality.value()}")

    # ---- daftar file ------------------------------------------------------

    def add_paths(self, paths: Iterable[str | Path]) -> None:
        if self._busy:
            return
        report = self.state.add(paths)
        self._render_list()
        parts = []
        if report.added:
            parts.append(f"{len(report.added)} file ditambahkan")
        if report.duplicates:
            parts.append(f"{len(report.duplicates)} sudah ada di daftar")
        if report.rejected:
            parts.append(f"{len(report.rejected)} ditolak")
        if parts:
            self._set_status(", ".join(parts) + ".")
        if report.rejected:
            box = QMessageBox(QMessageBox.Icon.Warning, "Sebagian file tidak ditambahkan",
                              "Hanya file JPG dan PNG yang bisa dikonversi.", QMessageBox.StandardButton.Ok, self)
            box.setDetailedText(summarize_rejections(report))
            box.exec()

    def _render_list(self, select_indices: Iterable[int] = ()) -> None:
        self.list_widget.set_entries(self.state.entries, select_indices)
        n = len(self.state)
        self.count_label.setText(f"{n} gambar, total {format_size(self.state.total_size)}" if n else "Belum ada gambar.")
        self._refresh_buttons()

    def _refresh_buttons(self) -> None:
        n = len(self.state)
        selected = self.list_widget.selected_indices()
        idle = not self._busy
        self.btn_add.setEnabled(idle)
        self.btn_remove.setEnabled(idle and bool(selected))
        self.btn_clear.setEnabled(idle and n > 0)
        self.btn_up.setEnabled(idle and bool(selected) and min(selected) > 0)
        self.btn_down.setEnabled(idle and bool(selected) and max(selected) < n - 1)
        self.btn_convert.setEnabled(idle and n > 0)
        self.list_widget.setEnabled(idle)
        self.settings_box.setEnabled(idle)

    def on_add_clicked(self) -> None:
        if self._busy:
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Pilih gambar", self._start_dir(), IMAGE_FILTER)
        if files:
            self.add_paths(files)

    def on_remove_clicked(self) -> None:
        if self._busy:
            return
        self.state.remove(self.list_widget.selected_indices())
        self._render_list()

    def on_clear_clicked(self) -> None:
        if self._busy:
            return
        self.state.clear()
        self._render_list()
        self._set_status("Daftar dikosongkan.")

    def on_move_up(self) -> None:
        self._render_list(self.state.move_up(self.list_widget.selected_indices()))

    def on_move_down(self) -> None:
        self._render_list(self.state.move_down(self.list_widget.selected_indices()))

    def on_move_requested(self, rows: list, target: int) -> None:
        if self._busy:
            return
        self._render_list(self.state.move_to(rows, target))

    # ---- konversi ---------------------------------------------------------

    def on_convert_clicked(self) -> None:
        if self._busy:
            return
        if len(self.state) == 0:
            self._set_status("Tambahkan gambar dulu.")
            return
        settings = self.read_settings()

        if settings.output_mode == "separate":
            folder = QFileDialog.getExistingDirectory(self, "Pilih folder tujuan", self._start_dir())
            if not folder:
                return
            output, overwrite = Path(folder), False
        else:
            suggested = Path(self._start_dir()) / suggest_output_name(self.state.paths)
            chosen, _ = QFileDialog.getSaveFileName(self, "Simpan PDF", str(suggested), "PDF (*.pdf)")
            if not chosen:
                return
            output = Path(chosen)
            # Dialog sistem sudah meminta konfirmasi jika file ada, jadi di sini boleh menimpa.
            overwrite = output.exists()
            if output.suffix.lower() != ".pdf":
                output = output.with_name(output.name + ".pdf")
                overwrite = False
        self.start_conversion(output, overwrite)

    def start_conversion(self, output: Path, overwrite: bool = False) -> None:
        """Mulai konversi di thread terpisah. Dipisah dari dialog agar bisa diuji."""
        if self._busy or len(self.state) == 0:
            return
        settings = self.read_settings()
        folder = output if settings.output_mode == "separate" else output.parent
        settings.last_output_dir = str(folder)
        self.user_settings = settings
        self.store.save(settings)

        worker = ConversionWorker(self.state.paths, output, settings.to_conversion_settings(overwrite))
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(lambda t=thread, w=worker: self._cleanup_thread(t, w))
        self._worker, self._thread = worker, thread

        self.progress.setRange(0, 0)  # sibuk (indeterminate) sampai laporan pertama
        self._set_busy(True)
        self._set_status("Memulai konversi...")
        thread.start()

    def on_cancel_clicked(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.btn_cancel.setEnabled(False)
            self._set_status("Membatalkan...")

    def _on_progress(self, step: int, total: int, label: str) -> None:
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(step)
        self._set_status(f"{label} ({step}/{total})")

    def _on_finished(self, result: ConversionResult) -> None:
        self._set_busy(False)
        self.conversion_finished.emit(result)
        self._show_result(result)

    def _on_failed(self, message: str) -> None:
        self._set_busy(False)
        self._set_status("Gagal.")
        self.last_error = message
        QMessageBox.critical(self, "Konversi gagal", message)

    def _cleanup_thread(self, thread: QThread, worker: ConversionWorker) -> None:
        worker.deleteLater()
        thread.deleteLater()
        if self._thread is thread:
            self._thread = None
            self._worker = None

    def _show_result(self, result: ConversionResult) -> None:
        summary = summarize_result(result, self.read_settings().output_mode)
        self._set_status(summary.title + ".")
        box = QMessageBox(_ICONS[summary.kind], summary.title, summary.text, QMessageBox.StandardButton.NoButton, self)
        if summary.details:
            box.setDetailedText(summary.details)
        open_button = None
        if summary.reveal_path is not None:
            open_button = box.addButton("Buka Folder", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Tutup", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if open_button is not None and box.clickedButton() is open_button:
            reveal_in_file_manager(summary.reveal_path)

    # ---- util -------------------------------------------------------------

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.progress.setVisible(busy)
        self.btn_cancel.setVisible(busy)
        self.btn_cancel.setEnabled(busy)
        self.btn_convert.setVisible(not busy)
        self._refresh_buttons()
        self._refresh_setting_states()

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _start_dir(self) -> str:
        last = self.user_settings.last_output_dir
        if last and Path(last).is_dir():
            return last
        if len(self.state):
            return str(self.state.paths[0].parent)
        return str(Path.home())

    # ---- menutup jendela --------------------------------------------------

    def closeEvent(self, event) -> None:
        if self._busy and self._worker is not None:
            answer = QMessageBox.question(
                self, "Konversi sedang berjalan", "Batalkan konversi dan keluar?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._worker.cancel()
            if self._thread is not None:
                # quit() dipanggil langsung: sinyal finished->quit bersifat antrean dan tidak
                # akan diproses selama thread utama menunggu di wait() (jadi macet).
                self._thread.quit()
                if not self._thread.wait(30000):
                    # Jangan menghancurkan QThread yang masih berjalan (bisa crash).
                    self._set_status("Masih membatalkan, coba tutup lagi sebentar lagi.")
                    event.ignore()
                    return
        self.list_widget.shutdown()
        self.store.save(self.read_settings())
        event.accept()
