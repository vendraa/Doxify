"""Membuat file info versi Windows untuk .exe (Properties > Details) dari app.__version__.

Info versi yang lengkap (nama produk, versi, deskripsi) juga sedikit mengurangi kecurigaan antivirus
terhadap .exe tanpa tanda tangan digital.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import __version__  # noqa: E402

PRODUCT = "Doxify"
DESCRIPTION = "Doxify - konverter JPG/PNG ke PDF, 100% offline"
COMPANY = "Doxify"

_TEMPLATE = """# UTF-8
# Dibuat otomatis oleh scripts/make_version_info.py. Jangan diedit manual.
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={tup},
    prodvers={tup},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', '{company}'),
         StringStruct('FileDescription', '{description}'),
         StringStruct('FileVersion', '{dotted}'),
         StringStruct('InternalName', '{product}'),
         StringStruct('OriginalFilename', '{product}.exe'),
         StringStruct('ProductName', '{product}'),
         StringStruct('ProductVersion', '{dotted}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def parse_version(version: str) -> tuple[int, int, int, int]:
    """'1.2.3' -> (1, 2, 3, 0). Hanya angka, 1-4 bagian, masing-masing 0-65535 (batas format Windows)."""
    if not re.fullmatch(r"\d+(\.\d+){0,3}", version):
        raise ValueError(f"Nomor versi tidak valid: {version!r} (contoh yang benar: 1.0.0)")
    parts = [int(p) for p in version.split(".")]
    if any(p > 65535 for p in parts):
        raise ValueError("Tiap bagian versi harus 0-65535")
    return tuple(parts + [0] * (4 - len(parts)))  # type: ignore[return-value]


def render(version: str = __version__) -> str:
    tup = parse_version(version)
    return _TEMPLATE.format(
        tup=tup, dotted=".".join(map(str, tup)), company=COMPANY, description=DESCRIPTION, product=PRODUCT
    )


def write_version_file(path: Path, version: str = __version__) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(version), encoding="utf-8")
    return path


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("build_meta/version_info.txt")
    print(f"Info versi ditulis: {write_version_file(target)}")
