"""Daftar gambar dengan drag-and-drop, urutan bisa diubah, dan thumbnail (FR-01, FR-05, FR-10)."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from PySide6.QtCore import QObject, QPoint, QRunnable, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QIcon, QImage, QImageReader, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem

from app.ui.logic import FileEntry, entry_key, format_size

THUMB_SIZE = 64
PATH_ROLE = Qt.ItemDataRole.UserRole
EMPTY_HINT = "Seret gambar JPG atau PNG ke sini\natau klik \"Tambah File\""


class _ThumbSignals(QObject):
    loaded = Signal(str, QImage)


class _ThumbTask(QRunnable):
    """Muat thumbnail di thread latar agar jendela tidak membeku."""

    def __init__(self, key: str, path: str, signals: _ThumbSignals) -> None:
        super().__init__()
        self._key = key
        self._path = path
        self._signals = signals
        self.setAutoDelete(True)

    def run(self) -> None:
        try:
            reader = QImageReader(self._path)
            reader.setAutoTransform(True)  # hormati rotasi EXIF
            size = reader.size()
            if size.isValid():
                limit = THUMB_SIZE * 2  # 2x agar tajam di layar HiDPI
                reader.setScaledSize(size.scaled(limit, limit, Qt.AspectRatioMode.KeepAspectRatio))
            image = reader.read()
            if not image.isNull():
                self._signals.loaded.emit(self._key, image)
        except Exception:  # noqa: BLE001 - thumbnail hanya hiasan, kegagalan diabaikan
            pass


class FileListWidget(QListWidget):
    """Sinyal:
    filesDropped(list[str])      file/folder dijatuhkan dari luar (mis. File Explorer)
    moveRequested(list[int], int) pengguna menyeret item ke posisi lain
    """

    filesDropped = Signal(list)
    moveRequested = Signal(list, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setIconSize(QSize(THUMB_SIZE, THUMB_SIZE))
        self.setSpacing(2)
        self.setUniformItemSizes(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        self._icons: dict[str, QIcon] = {}
        self._pending: set[str] = set()
        self._placeholder = self._make_placeholder()
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(2)
        self._signals = _ThumbSignals(self)
        self._signals.loaded.connect(self._on_thumbnail)

    # ---- data -------------------------------------------------------------

    def paths(self) -> list[str]:
        return [self.item(i).data(PATH_ROLE) for i in range(self.count())]

    def selected_indices(self) -> list[int]:
        return sorted(self.row(item) for item in self.selectedItems())

    def set_entries(self, entries: Sequence[FileEntry], select_indices: Iterable[int] = ()) -> None:
        """Gambar ulang seluruh daftar dari state (state adalah sumber kebenaran)."""
        selected = set(select_indices)
        keep = {entry_key(e.path) for e in entries}
        self._icons = {k: v for k, v in self._icons.items() if k in keep}

        self.clear()
        for index, entry in enumerate(entries):
            item = QListWidgetItem(self._icon_for(entry), f"{index + 1}.  {entry.name}\n{format_size(entry.size)}")
            item.setData(PATH_ROLE, str(entry.path))
            item.setToolTip(str(entry.path))
            self.addItem(item)
            if index in selected:
                item.setSelected(True)

    # ---- thumbnail --------------------------------------------------------

    def _make_placeholder(self) -> QIcon:
        pixmap = QPixmap(THUMB_SIZE, THUMB_SIZE)
        pixmap.fill(self.palette().color(QPalette.ColorRole.Midlight))
        return QIcon(pixmap)

    def _icon_for(self, entry: FileEntry) -> QIcon:
        key = entry_key(entry.path)
        icon = self._icons.get(key)
        if icon is not None:
            return icon
        if key not in self._pending:
            self._pending.add(key)
            self._pool.start(_ThumbTask(key, str(entry.path), self._signals))
        return self._placeholder

    def _on_thumbnail(self, key: str, image: QImage) -> None:
        self._pending.discard(key)
        icon = QIcon(QPixmap.fromImage(image))
        self._icons[key] = icon
        for i in range(self.count()):
            item = self.item(i)
            if entry_key(Path(item.data(PATH_ROLE))) == key:
                item.setIcon(icon)

    def shutdown(self) -> None:
        """Hentikan thread thumbnail sebelum jendela ditutup."""
        self._pool.clear()
        self._pool.waitForDone(3000)

    # ---- drag-and-drop ----------------------------------------------------

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        mime = event.mimeData()
        if mime.hasUrls() and event.source() is not self:
            paths = [url.toLocalFile() for url in mime.urls() if url.isLocalFile()]
            event.acceptProposedAction()
            if paths:
                self.filesDropped.emit(paths)
            return
        if event.source() is self:
            # Urutan diubah lewat state (bukan lewat model Qt) supaya tetap konsisten.
            rows = self.selected_indices()
            target = self._target_row(event.position().toPoint())
            event.setDropAction(Qt.DropAction.IgnoreAction)
            event.accept()
            if rows:
                self.moveRequested.emit(rows, target)
            return
        event.ignore()

    def _target_row(self, pos: QPoint) -> int:
        item = self.itemAt(pos)
        if item is None:
            return self.count()
        rect = self.visualItemRect(item)
        return self.row(item) + (1 if pos.y() > rect.center().y() else 0)

    # ---- tampilan kosong --------------------------------------------------

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self.count() == 0:
            painter = QPainter(self.viewport())
            painter.setPen(self.palette().color(QPalette.ColorRole.PlaceholderText))
            painter.drawText(self.viewport().rect(), Qt.AlignmentFlag.AlignCenter, EMPTY_HINT)
            painter.end()
