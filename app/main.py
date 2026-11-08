"""Titik masuk Doxify. Jalankan dengan:  python -m app.main [file ...]"""
from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)

    from PySide6.QtWidgets import QApplication

    from app import __version__
    from app.ui.main_window import MainWindow
    from app.utils.temp import cleanup_stale_temp_dirs

    cleanup_stale_temp_dirs()  # bersihkan sisa temp dari crash sebelumnya

    app = QApplication(argv)
    app.setApplicationName("Doxify")
    app.setOrganizationName("Doxify")
    app.setApplicationVersion(__version__)

    window = MainWindow()
    window.show()
    if len(argv) > 1:  # mis. "Buka dengan" / "Kirim ke" dari Windows Explorer
        window.add_paths(argv[1:])
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
