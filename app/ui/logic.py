"""Logika antarmuka yang TIDAK bergantung pada Qt, sehingga bisa diuji penuh.

Lapisan Qt (main_window.py, file_list.py) hanya menampilkan state dari modul ini.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from app.converters.base import ConversionResult, OutputMode
from app.converters.image import SUPPORTED_EXTENSIONS

MAX_DETAIL_LINES = 20


def entry_key(path: str | Path) -> str:
    """Kunci pembanding path (huruf besar/kecil tidak dibedakan di Windows)."""
    return os.path.normcase(os.path.abspath(path))


def natural_key(name: str) -> list:
    """Urutan alami: foto2.jpg sebelum foto10.jpg."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def format_size(num_bytes: int) -> str:
    """Ukuran file dengan koma desimal gaya Indonesia, mis. '2,4 MB'."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    value = float(num_bytes)
    for unit in ("KB", "MB", "GB"):
        value /= 1024
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}".replace(".", ",")
    raise AssertionError("tidak tercapai")


@dataclass(frozen=True)
class FileEntry:
    path: Path
    size: int

    @property
    def name(self) -> str:
        return self.path.name


@dataclass
class AddReport:
    added: list[Path] = field(default_factory=list)
    duplicates: list[Path] = field(default_factory=list)
    rejected: list[tuple[Path, str]] = field(default_factory=list)


class FileListState:
    """Daftar gambar yang akan dikonversi; urutan daftar = urutan halaman PDF."""

    def __init__(self) -> None:
        self._entries: list[FileEntry] = []

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def entries(self) -> tuple[FileEntry, ...]:
        return tuple(self._entries)

    @property
    def paths(self) -> list[Path]:
        return [e.path for e in self._entries]

    @property
    def total_size(self) -> int:
        return sum(e.size for e in self._entries)

    # ---- menambah ---------------------------------------------------------

    def add(self, raw_paths: Iterable[str | Path]) -> AddReport:
        """Tambah file/folder. Folder diperluas (tidak rekursif) dengan urutan alami."""
        report = AddReport()
        known = {entry_key(e.path) for e in self._entries}

        for raw in raw_paths:
            path = Path(raw)
            for candidate in self._expand(path, report):
                key = entry_key(candidate)
                if key in known:
                    report.duplicates.append(candidate)
                    continue
                if candidate.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    report.rejected.append((candidate, "Format tidak didukung (hanya JPG dan PNG)."))
                    continue
                try:
                    size = candidate.stat().st_size
                except OSError:
                    report.rejected.append((candidate, "File tidak ditemukan atau tidak bisa dibaca."))
                    continue
                known.add(key)
                self._entries.append(FileEntry(candidate, size))
                report.added.append(candidate)
        return report

    @staticmethod
    def _expand(path: Path, report: AddReport) -> list[Path]:
        if not path.is_dir():
            return [path]
        try:
            files = [p for p in path.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
        except OSError:
            report.rejected.append((path, "Folder tidak bisa dibaca."))
            return []
        if not files:
            report.rejected.append((path, "Folder tidak berisi gambar JPG atau PNG."))
            return []
        return sorted(files, key=lambda p: natural_key(p.name))

    # ---- mengubah daftar --------------------------------------------------

    def _valid(self, indices: Iterable[int]) -> list[int]:
        return sorted({i for i in indices if 0 <= i < len(self._entries)})

    def remove(self, indices: Iterable[int]) -> None:
        drop = set(self._valid(indices))
        self._entries = [e for i, e in enumerate(self._entries) if i not in drop]

    def clear(self) -> None:
        self._entries = []

    def move_up(self, indices: Iterable[int]) -> list[int]:
        """Geser item terpilih satu posisi ke atas. Mengembalikan indeks barunya."""
        return self._shift(indices, up=True)

    def move_down(self, indices: Iterable[int]) -> list[int]:
        return self._shift(indices, up=False)

    def _shift(self, indices: Iterable[int], up: bool) -> list[int]:
        selected = set(self._valid(indices))
        items = [(e, i in selected) for i, e in enumerate(self._entries)]
        order = range(1, len(items)) if up else range(len(items) - 2, -1, -1)
        for i in order:
            a, b = (i - 1, i) if up else (i + 1, i)
            if items[b][1] and not items[a][1]:
                items[a], items[b] = items[b], items[a]
        self._entries = [e for e, _ in items]
        return [i for i, (_, sel) in enumerate(items) if sel]

    def move_to(self, indices: Iterable[int], target_row: int) -> list[int]:
        """Pindahkan item terpilih ke posisi target (hasil drag-and-drop).

        `target_row` = baris tempat item dijatuhkan, dihitung sebelum item dipindah.
        Mengembalikan indeks baru item yang dipindah.
        """
        selected = self._valid(indices)
        if not selected:
            return []
        chosen = set(selected)
        moving = [self._entries[i] for i in selected]
        rest = [e for i, e in enumerate(self._entries) if i not in chosen]
        target = max(0, min(len(self._entries), target_row))
        insert_at = max(0, min(len(rest), target - sum(1 for i in selected if i < target)))
        self._entries = rest[:insert_at] + moving + rest[insert_at:]
        return list(range(insert_at, insert_at + len(moving)))


# ---- nama file dan ringkasan hasil -------------------------------------------


def suggest_output_name(paths: Sequence[Path]) -> str:
    if len(paths) == 1:
        return paths[0].stem + ".pdf"
    return "gabungan.pdf"


@dataclass(frozen=True)
class ResultSummary:
    kind: str  # "success" | "warning" | "error" | "cancelled"
    title: str
    text: str
    details: str = ""
    reveal_path: Path | None = None


def summarize_result(result: ConversionResult, mode: OutputMode | str) -> ResultSummary:
    """Ringkasan untuk ditampilkan ke pengguna setelah konversi (FR-34, US-6)."""
    mode = OutputMode(mode)
    details = _failure_details(result)
    reveal = result.outputs[0] if result.outputs else None
    n_ok, n_fail = len(result.converted), len(result.failed)

    if result.cancelled:
        if result.outputs:
            text = f"Konversi dibatalkan. {len(result.outputs)} PDF sudah tersimpan sebelum dibatalkan."
        else:
            text = "Konversi dibatalkan. Tidak ada file yang disimpan."
        return ResultSummary("cancelled", "Dibatalkan", text, details, reveal)

    if not result.outputs:
        return ResultSummary(
            "error", "Tidak ada PDF yang dibuat",
            "Semua file dilewati karena tidak valid. Lihat rincian untuk alasannya.", details,
        )

    if mode is OutputMode.MERGED:
        text = f"{n_ok} gambar digabung menjadi 1 PDF:\n{reveal.name}"
    else:
        folder = reveal.parent
        text = f"{len(result.outputs)} PDF dibuat di folder:\n{folder}"

    if n_fail:
        text += f"\n\n{n_ok} berhasil, {n_fail} dilewati."
        return ResultSummary("warning", "Selesai dengan peringatan", text, details, reveal)
    return ResultSummary("success", "Konversi selesai", text, details, reveal)


def _failure_details(result: ConversionResult) -> str:
    lines = [f"{f.path.name}: {f.reason}" for f in result.failed[:MAX_DETAIL_LINES]]
    extra = len(result.failed) - MAX_DETAIL_LINES
    if extra > 0:
        lines.append(f"... dan {extra} file lainnya.")
    return "\n".join(lines)


def summarize_rejections(report: AddReport) -> str:
    """Teks untuk file yang ditolak saat ditambahkan ke daftar."""
    lines = [f"{p.name}: {reason}" for p, reason in report.rejected[:MAX_DETAIL_LINES]]
    extra = len(report.rejected) - MAX_DETAIL_LINES
    if extra > 0:
        lines.append(f"... dan {extra} file lainnya.")
    return "\n".join(lines)
