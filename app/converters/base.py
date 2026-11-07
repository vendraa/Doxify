"""Tipe data bersama dan antarmuka dasar untuk semua converter Doxify.

Modul ini TIDAK boleh mengimpor apa pun dari ui/ (NFR-08).
"""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, ClassVar, Iterable


class PageSize(str, Enum):
    A4 = "a4"
    LETTER = "letter"
    ORIGINAL = "original"


class Orientation(str, Enum):
    AUTO = "auto"
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class Margin(str, Enum):
    NONE = "none"
    SMALL = "small"
    MEDIUM = "medium"


class Quality(str, Enum):
    ORIGINAL = "original"
    COMPRESSED = "compressed"


class OutputMode(str, Enum):
    MERGED = "merged"
    SEPARATE = "separate"


@dataclass(frozen=True)
class ConversionSettings:
    """Pengaturan konversi (FR-20 s.d. FR-26). Nilai default = default di PRD."""

    page_size: PageSize = PageSize.A4
    orientation: Orientation = Orientation.AUTO
    margin: Margin = Margin.SMALL
    quality: Quality = Quality.ORIGINAL
    jpeg_quality: int = 75  # dipakai hanya pada Quality.COMPRESSED
    max_long_edge: int | None = 3508  # px sisi terpanjang pada mode terkompres (A4 @ 300 dpi)
    strip_metadata: bool = True
    output_mode: OutputMode = OutputMode.MERGED
    overwrite: bool = False

    def __post_init__(self) -> None:
        # Terima string biasa (dari CLI/GUI) dan ubah ke Enum.
        for name, enum_cls in (
            ("page_size", PageSize),
            ("orientation", Orientation),
            ("margin", Margin),
            ("quality", Quality),
            ("output_mode", OutputMode),
        ):
            object.__setattr__(self, name, enum_cls(getattr(self, name)))
        if not 1 <= self.jpeg_quality <= 95:
            raise ValueError("jpeg_quality harus antara 1 dan 95")
        if self.max_long_edge is not None and self.max_long_edge < 100:
            raise ValueError("max_long_edge terlalu kecil")


class DoxifyError(Exception):
    """Kesalahan yang pesannya aman ditampilkan langsung ke pengguna."""


class InvalidImageError(DoxifyError):
    """File gambar tidak valid, rusak, atau tidak didukung."""


class OutputError(DoxifyError):
    """Gagal menulis file hasil (izin, disk penuh, file sedang dipakai)."""


class ConversionCancelled(DoxifyError):
    """Pengguna membatalkan konversi."""


class CancelToken:
    """Penanda pembatalan yang aman dipakai lintas thread (FR-33)."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self._event.is_set():
            raise ConversionCancelled("Konversi dibatalkan.")


# (langkah_sekarang, total_langkah, keterangan)
ProgressCallback = Callable[[int, int, str], None]


@dataclass
class FailedFile:
    path: Path
    reason: str


@dataclass
class ConversionResult:
    outputs: list[Path] = field(default_factory=list)  # PDF yang dihasilkan
    converted: list[Path] = field(default_factory=list)  # gambar yang berhasil
    failed: list[FailedFile] = field(default_factory=list)  # gambar yang dilewati
    cancelled: bool = False

    @property
    def ok(self) -> bool:
        return bool(self.outputs) and not self.failed and not self.cancelled


class BaseConverter(ABC):
    """Antarmuka yang sama untuk semua converter (image sekarang, office nanti)."""

    extensions: ClassVar[frozenset[str]]

    @classmethod
    def supports(cls, path: str | Path) -> bool:
        return Path(path).suffix.lower() in cls.extensions

    @abstractmethod
    def convert(
        self,
        inputs: Iterable[str | Path],
        output: str | Path,
        settings: ConversionSettings | None = None,
        progress: ProgressCallback | None = None,
        cancel: CancelToken | None = None,
    ) -> ConversionResult:
        """Konversi `inputs` ke PDF. Lihat implementasi untuk arti `output`."""
