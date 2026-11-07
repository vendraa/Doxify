"""Penyimpanan pengaturan pengguna secara lokal (FR-27).

Yang disimpan HANYA pilihan pengaturan dan folder tujuan terakhir. Nama file
gambar tidak pernah disimpan (NFR-02). Kegagalan baca/tulis tidak pernah membuat
aplikasi error: pengaturan kembali ke default.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

from app.converters.base import (
    ConversionSettings,
    Margin,
    Orientation,
    OutputMode,
    PageSize,
    Quality,
)

MIN_UI_JPEG_QUALITY = 30
MAX_JPEG_QUALITY = 95


def default_settings_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
        return base / "Doxify" / "settings.json"
    base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    return base / "doxify" / "settings.json"


def _enum_value(enum_cls: type[Enum], value, default: str) -> str:
    try:
        return enum_cls(value).value
    except ValueError:
        return default


@dataclass
class UserSettings:
    """Nilai disimpan sebagai string biasa agar mudah dipakai di widget Qt."""

    output_mode: str = OutputMode.MERGED.value
    page_size: str = PageSize.A4.value
    orientation: str = Orientation.AUTO.value
    margin: str = Margin.SMALL.value
    quality: str = Quality.ORIGINAL.value
    jpeg_quality: int = 75
    strip_metadata: bool = True
    last_output_dir: str = ""

    def to_conversion_settings(self, overwrite: bool = False) -> ConversionSettings:
        return ConversionSettings(
            page_size=self.page_size,
            orientation=self.orientation,
            margin=self.margin,
            quality=self.quality,
            jpeg_quality=self.jpeg_quality,
            strip_metadata=self.strip_metadata,
            output_mode=self.output_mode,
            overwrite=overwrite,
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: object) -> "UserSettings":
        """Baca dari dict apa pun; nilai tidak valid diganti default (tidak error)."""
        d = cls()
        if not isinstance(data, dict):
            return d
        return cls(
            output_mode=_enum_value(OutputMode, data.get("output_mode"), d.output_mode),
            page_size=_enum_value(PageSize, data.get("page_size"), d.page_size),
            orientation=_enum_value(Orientation, data.get("orientation"), d.orientation),
            margin=_enum_value(Margin, data.get("margin"), d.margin),
            quality=_enum_value(Quality, data.get("quality"), d.quality),
            jpeg_quality=_clamp_int(data.get("jpeg_quality"), MIN_UI_JPEG_QUALITY, MAX_JPEG_QUALITY, d.jpeg_quality),
            strip_metadata=data["strip_metadata"] if isinstance(data.get("strip_metadata"), bool) else d.strip_metadata,
            last_output_dir=data["last_output_dir"] if isinstance(data.get("last_output_dir"), str) else "",
        )


def _clamp_int(value, low: int, high: int, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return max(low, min(high, value))


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else default_settings_path()

    def load(self) -> UserSettings:
        try:
            return UserSettings.from_dict(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return UserSettings()

    def save(self, settings: UserSettings) -> bool:
        """Simpan secara atomik. Mengembalikan False (tanpa error) jika gagal."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".settings-", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(settings.to_dict(), fh, ensure_ascii=False, indent=2)
                os.replace(tmp, self.path)
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
            return True
        except OSError:
            return False
