"""Folder sementara dengan nama acak yang selalu dibersihkan (bagian 9 PRD)."""
from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path

TEMP_PREFIX = "doxify_"


class SessionTempDir:
    """Context manager: buat folder temp acak, hapus isinya saat selesai/gagal/dibatalkan."""

    def __init__(self) -> None:
        self.path: Path | None = None

    def __enter__(self) -> Path:
        self.path = Path(tempfile.mkdtemp(prefix=TEMP_PREFIX))
        return self.path

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.path is not None:
            shutil.rmtree(self.path, ignore_errors=True)
            self.path = None


def cleanup_stale_temp_dirs(max_age_seconds: float = 600, base: Path | None = None) -> int:
    """Hapus folder temp Doxify sisa crash. Panggil sekali saat aplikasi dibuka.

    Hanya folder berawalan 'doxify_' yang lebih tua dari max_age_seconds yang dihapus,
    supaya tidak mengganggu proses lain yang sedang berjalan.
    """
    base = base or Path(tempfile.gettempdir())
    removed = 0
    now = time.time()
    try:
        entries = list(base.iterdir())
    except OSError:
        return 0
    for entry in entries:
        if not entry.is_dir() or not entry.name.startswith(TEMP_PREFIX):
            continue
        try:
            if now - entry.stat().st_mtime >= max_age_seconds:
                shutil.rmtree(entry, ignore_errors=True)
                removed += 1
        except OSError:
            continue
    return removed
