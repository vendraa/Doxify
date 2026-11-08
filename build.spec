# -*- mode: python ; coding: utf-8 -*-
# Konfigurasi PyInstaller untuk Doxify. Jalankan lewat scripts/windows/build.ps1
# (atau manual: python -m PyInstaller --noconfirm --clean build.spec).
#
# Keputusan penting:
#  - mode folder (onedir), bukan satu file: lebih jarang dianggap mencurigakan oleh antivirus
#  - UPX dimatikan: file terkompresi UPX sering memicu false positive
#  - console=False: aplikasi jendela, tanpa jendela hitam
#  - modul jaringan sengaja dikecualikan: aplikasi ini tidak pernah memakai jaringan
import sys
from pathlib import Path

ROOT = Path(SPECPATH)
sys.path.insert(0, str(ROOT / "scripts"))
from make_version_info import write_version_file  # noqa: E402

ICON = ROOT / "assets" / "doxify.ico"
if not ICON.is_file():
    raise SystemExit("assets/doxify.ico tidak ditemukan. Jalankan: python scripts/make_icon.py")
VERSION_FILE = write_version_file(ROOT / "build_meta" / "version_info.txt")

EXCLUDES = [
    # jaringan
    "ssl", "http", "urllib.request", "ftplib", "smtplib", "imaplib", "poplib", "nntplib", "telnetlib", "xmlrpc",
    "PySide6.QtNetwork", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebSockets",
    "PySide6.QtWebChannel", "PySide6.QtNetworkAuth", "PySide6.QtHttpServer",
    # Qt yang tidak dipakai (memperkecil ukuran)
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets", "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.Qt3DCore",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtBluetooth", "PySide6.QtNfc",
    "PySide6.QtPositioning", "PySide6.QtSensors", "PySide6.QtSerialPort", "PySide6.QtDesigner",
    # perkakas pengembangan
    "tkinter", "unittest", "pydoc", "test", "pytest", "pypdf",
]

a = Analysis(
    [str(ROOT / "run_doxify.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    excludes=EXCLUDES,
    noarchive=False,
)
# PyInstaller 6.22 can collect Qt6Network.dll as a transitive binary even when
# PySide6.QtNetwork is excluded. The app is intentionally offline, so remove
# that runtime binary from the collected package as well.
a.binaries = [entry for entry in a.binaries if Path(entry[0]).name.lower() != "qt6network.dll"]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Doxify",
    console=False,
    icon=str(ICON),
    version=str(VERSION_FILE),
    upx=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Doxify",
)
