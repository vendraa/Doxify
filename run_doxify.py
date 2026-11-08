"""Titik masuk untuk .exe hasil PyInstaller dan untuk `python run_doxify.py`.

    Doxify.exe                              buka aplikasi
    Doxify.exe foto1.jpg foto2.png          buka aplikasi dengan file langsung ditambahkan
    Doxify.exe --self-test hasil.txt        uji mandiri (menulis laporan ke hasil.txt, kode keluar 0 = lulus)
    Doxify.exe --self-test --no-gui         uji mandiri tanpa memeriksa Qt
"""
import os
import sys


def _ensure_std_streams() -> None:
    # Mode windowed (tanpa konsol): sys.stdout/sys.stderr bernilai None, dan library yang
    # mencetak sesuatu bisa crash. Arahkan ke "kosong" supaya aman.
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))


def main(argv: list[str]) -> int:
    _ensure_std_streams()
    if len(argv) > 1 and argv[1] == "--self-test":
        rest = argv[2:]
        report = next((a for a in rest if not a.startswith("--")), None)
        from app.selftest import run

        return run(report, require_qt="--no-gui" not in rest)
    from app.main import main as app_main

    return app_main(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
