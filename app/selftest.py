"""Uji mandiri (`Doxify.exe --self-test`): membuktikan bahwa hasil build/instalasi benar-benar bekerja.

Dijalankan terhadap .exe hasil PyInstaller, pemeriksaan ini mencakup hal-hal yang tidak bisa dibuktikan
oleh tes biasa: apakah semua library dan plugin Qt ikut terbungkus, apakah konversi berjalan di dalam
paket, dan apakah ada upaya koneksi jaringan selama pemeriksaan berlangsung.
"""
from __future__ import annotations

import platform
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

from app import __version__

PASS, FAIL, SKIP = "LULUS", "GAGAL", "DILEWATI"


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""


class _SkipCheck(Exception):
    """Dilempar sebuah pemeriksaan untuk menandai dirinya dilewati."""


# ---- pemantau jaringan -------------------------------------------------------


class NetworkWatch:
    """Mencatat dan menggagalkan setiap upaya koneksi jaringan dari Python selama diaktifkan."""

    def __init__(self) -> None:
        self.attempts: list[str] = []
        self.socket_available = True

    @contextmanager
    def active(self) -> Iterator["NetworkWatch"]:
        try:
            import socket
        except ImportError:  # modul memang tidak ada di paket
            self.socket_available = False
            yield self
            return

        def make_guard(name: str) -> Callable:
            def guard(*args, **kwargs):
                target = args[0] if args else ""
                if name in ("connect", "connect_ex", "sendto") and len(args) > 1:
                    target = args[1]
                self.attempts.append(f"{name}({target!r})")
                raise OSError(f"Doxify memblokir koneksi jaringan ({name})")

            return guard

        patched: list[tuple[object, str, object]] = []
        for owner, names in (
            (socket.socket, ("connect", "connect_ex", "sendto")),
            (socket, ("getaddrinfo", "gethostbyname", "create_connection")),
        ):
            for attr in names:
                patched.append((owner, attr, getattr(owner, attr)))
                setattr(owner, attr, make_guard(attr))
        try:
            yield self
        finally:
            for owner, attr, original in patched:
                setattr(owner, attr, original)


# ---- pemeriksaan -------------------------------------------------------------


def _count_pages(pdf: Path) -> int:
    try:
        import pikepdf

        with pikepdf.open(pdf) as doc:
            return len(doc.pages)
    except ImportError:
        import re

        return len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", pdf.read_bytes()))


def _check_conversion(work: Path) -> str:
    from PIL import Image

    from app.converters import ConversionSettings, ImageConverter

    jpg, png = work / "uji.jpg", work / "uji.png"
    Image.new("RGB", (320, 200), (30, 90, 160)).save(jpg, quality=90)
    Image.new("RGBA", (120, 120), (200, 20, 20, 100)).save(png)
    result = ImageConverter().convert([jpg, png], work / "hasil.pdf", ConversionSettings())
    if not result.ok:
        raise AssertionError(f"konversi gagal: {[f.reason for f in result.failed]}")
    data = result.outputs[0].read_bytes()
    if not data.startswith(b"%PDF-"):
        raise AssertionError("hasil bukan PDF")
    pages = _count_pages(result.outputs[0])
    if pages != 2:
        raise AssertionError(f"jumlah halaman {pages}, seharusnya 2")
    return f"JPG + PNG transparan menjadi PDF {pages} halaman"


def _check_compressed(work: Path) -> str:
    from PIL import Image

    from app.converters import ConversionSettings, ImageConverter

    jpg = work / "kompres.jpg"
    Image.new("RGB", (800, 600), (200, 120, 40)).save(jpg, quality=95)
    result = ImageConverter().convert([jpg], work / "kompres.pdf", ConversionSettings(quality="compressed"))
    if not result.ok:
        raise AssertionError("mode terkompres gagal")
    return "mode terkompres berjalan"


def _check_metadata_removed(work: Path) -> str:
    from PIL import Image

    from app.converters import ConversionSettings, ImageConverter

    exif = Image.Exif()
    exif[0x010F] = "SelfTestCam"
    exif[0x0112] = 6
    exif[0x8825] = {1: "S", 2: (6.0, 59.0, 0.0), 3: "E", 4: (110.0, 24.0, 0.0)}
    jpg = work / "exif.jpg"
    Image.new("RGB", (200, 100), (10, 120, 60)).save(jpg, exif=exif)
    result = ImageConverter().convert([jpg], work / "exif.pdf", ConversionSettings())
    if not result.ok:
        raise AssertionError("konversi gambar ber-EXIF gagal")
    if b"SelfTestCam" in result.outputs[0].read_bytes():
        raise AssertionError("metadata kamera masih ada di PDF")
    return "EXIF/GPS tidak ikut masuk ke PDF"


def _check_settings(work: Path) -> str:
    from app.utils.settings_store import SettingsStore, UserSettings

    store = SettingsStore(work / "cfg" / "settings.json")
    wanted = UserSettings(page_size="letter", jpeg_quality=60, strip_metadata=False)
    if not store.save(wanted) or store.load() != wanted:
        raise AssertionError("pengaturan tidak tersimpan/terbaca")
    return "pengaturan tersimpan dan terbaca"


def _check_qt(work: Path) -> str:
    try:
        from PySide6.QtGui import QImageReader
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        raise AssertionError(f"PySide6 tidak bisa dimuat: {exc}") from exc

    from app.converters import ConversionSettings  # noqa: F401  (memastikan paket converters ikut terbungkus)
    from app.ui.main_window import MainWindow
    from app.utils.settings_store import SettingsStore
    from PIL import Image

    app = QApplication.instance() or QApplication(["doxify-selftest"])
    formats = {bytes(f).decode().lower() for f in QImageReader.supportedImageFormats()}
    missing = {"jpeg", "png"} - formats
    if missing:
        raise AssertionError(f"plugin gambar Qt tidak lengkap, hilang: {sorted(missing)}")

    jpg = work / "gui.jpg"
    Image.new("RGB", (64, 64), (1, 2, 3)).save(jpg)
    window = MainWindow(SettingsStore(work / "gui" / "settings.json"))
    window.add_paths([jpg])
    count = window.list_widget.count()
    window.close()
    app.processEvents()
    if count != 1:
        raise AssertionError(f"daftar file berisi {count} item, seharusnya 1")
    return "jendela utama terbentuk, plugin gambar Qt lengkap (jpeg, png)"


# ---- pelaksana ---------------------------------------------------------------


def run(
    report_path: str | Path | None = None,
    require_qt: bool = True,
    extra_checks: list[tuple[str, Callable[[Path], str]]] | None = None,
) -> int:
    """Jalankan semua pemeriksaan. Mengembalikan 0 jika semuanya lulus, 1 jika ada yang gagal."""
    checks: list[tuple[str, Callable[[Path], str]]] = [
        ("Konversi JPG + PNG ke PDF", _check_conversion),
        ("Konversi mode terkompres", _check_compressed),
        ("Penghapusan metadata EXIF/GPS", _check_metadata_removed),
        ("Penyimpanan pengaturan", _check_settings),
    ]
    if require_qt:
        checks.append(("Antarmuka Qt (GUI)", _check_qt))
    checks.extend(extra_checks or [])

    results: list[Check] = []
    watch = NetworkWatch()
    with tempfile.TemporaryDirectory(prefix="doxify_selftest_") as tmp, watch.active():
        work = Path(tmp)
        for name, func in checks:
            try:
                results.append(Check(name, PASS, func(work)))
            except _SkipCheck as exc:
                results.append(Check(name, SKIP, str(exc)))
            except Exception as exc:  # noqa: BLE001 - tujuan self-test: melaporkan apa pun yang rusak
                results.append(Check(name, FAIL, f"{exc.__class__.__name__}: {exc}"))

    if not watch.socket_available:
        results.append(Check("Tanpa koneksi jaringan", PASS, "modul socket tidak ada di paket"))
    elif watch.attempts:
        results.append(Check("Tanpa koneksi jaringan", FAIL, "ada upaya koneksi: " + "; ".join(watch.attempts[:5])))
    else:
        results.append(Check("Tanpa koneksi jaringan", PASS, "tidak ada upaya koneksi selama pemeriksaan"))

    failed = [c for c in results if c.status == FAIL]
    lines = [
        f"Doxify {__version__} - uji mandiri",
        f"Python {platform.python_version()} | {platform.platform()} | paket PyInstaller: {bool(getattr(sys, 'frozen', False))}",
        "",
    ]
    lines += [f"[{c.status}] {c.name}" + (f" - {c.detail}" if c.detail else "") for c in results]
    lines += ["", "HASIL: " + ("LULUS" if not failed else f"GAGAL ({len(failed)} pemeriksaan)")]
    text = "\n".join(lines) + "\n"

    if report_path:
        Path(report_path).write_text(text, encoding="utf-8")
    elif sys.stdout is not None:
        sys.stdout.write(text)
    return 0 if not failed else 1
