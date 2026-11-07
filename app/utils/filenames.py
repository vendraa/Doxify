"""Pembersihan nama file output agar aman di Windows (FR-41, FR-42)."""
from __future__ import annotations

import re
from pathlib import Path

_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL"}
_RESERVED |= {f"COM{i}" for i in range(1, 10)}
_RESERVED |= {f"LPT{i}" for i in range(1, 10)}

DEFAULT_STEM = "dokumen"
MAX_STEM_LENGTH = 100
# Di bawah batas klasik MAX_PATH Windows (260) agar aman di semua aplikasi.
MAX_PATH_LENGTH = 240


def sanitize_stem(name: str, max_length: int = MAX_STEM_LENGTH) -> str:
    """Bersihkan nama file (tanpa ekstensi) dari karakter terlarang Windows."""
    stem = _FORBIDDEN.sub("_", name).strip(" .")
    if not stem:
        return DEFAULT_STEM
    if stem.split(".")[0].upper() in _RESERVED:
        stem = "_" + stem
    return stem[:max_length].rstrip(" .") or DEFAULT_STEM


def build_pdf_path(directory: str | Path, name: str) -> Path:
    """Gabungkan folder + nama menjadi path PDF yang valid dan tidak terlalu panjang."""
    directory = Path(directory)
    stem = name[:-4] if name.lower().endswith(".pdf") else name
    stem = sanitize_stem(stem)
    # sisakan ruang untuk ".pdf" dan akhiran " (99)" dari unique_path
    room = MAX_PATH_LENGTH - len(str(directory)) - 1 - len(".pdf") - len(" (99)")
    if room < 8:
        raise ValueError("Path folder tujuan terlalu panjang. Pilih folder yang lebih pendek.")
    stem = stem[:room].rstrip(" .") or DEFAULT_STEM
    return directory / f"{stem}.pdf"


def unique_path(path: Path) -> Path:
    """Jika path sudah ada, tambahkan akhiran ' (1)', ' (2)', dst. Tidak menimpa file."""
    if not path.exists():
        return path
    for n in range(1, 10_000):
        candidate = path.with_name(f"{path.stem} ({n}){path.suffix}")
        if not candidate.exists():
            return candidate
    raise ValueError("Terlalu banyak file dengan nama yang sama di folder tujuan.")
