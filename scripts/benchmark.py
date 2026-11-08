"""Benchmark kecepatan dan memori konversi (NFR-03, NFR-04, NFR-05).

    python scripts/benchmark.py              # 20 foto ~5 MB, lalu 60 foto, lalu 1 gambar sangat besar
    python scripts/benchmark.py --photos 20 --size-mb 5

Semua gambar dibuat sementara dan dihapus setelah selesai. Hasilnya memakai CPU
dan disk komputermu sendiri, jadi angkanya mencerminkan laptopmu.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from app.converters import ConversionSettings, ImageConverter  # noqa: E402


def peak_memory_mb() -> float:
    """Puncak pemakaian memori proses ini (MB). Mendukung Windows dan Linux/macOS."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
        return counters.PeakWorkingSetSize / 1024 / 1024
    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / 1024 / 1024 if sys.platform == "darwin" else peak / 1024


def make_photo(path: Path, target_mb: float, seed: int) -> None:
    """Foto bernoise ukuran ~target_mb (noise sulit dikompres, jadi mendekati foto asli)."""
    width, height = 4000, 3000
    img = Image.effect_noise((width, height), 40 + seed % 30).convert("RGB")
    quality = 92
    img.save(path, "JPEG", quality=quality)
    while path.stat().st_size / 1024 / 1024 > target_mb * 1.15 and quality > 40:
        quality -= 8
        img.save(path, "JPEG", quality=quality)


def run_case(label: str, files: list[Path], out_dir: Path, settings: ConversionSettings) -> None:
    start = time.perf_counter()
    result = ImageConverter().convert(files, out_dir / f"{label}.pdf", settings)
    elapsed = time.perf_counter() - start
    pdf_mb = result.outputs[0].stat().st_size / 1024 / 1024 if result.outputs else 0
    print(f"{label:<34} {len(files):>3} gambar | {elapsed:6.1f} dtk | PDF {pdf_mb:7.1f} MB | "
          f"memori puncak proses {peak_memory_mb():7.0f} MB | gagal: {len(result.failed)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--photos", type=int, default=20)
    parser.add_argument("--size-mb", type=float, default=5.0)
    parser.add_argument("--skip-large", action="store_true")
    args = parser.parse_args()

    work = Path(tempfile.mkdtemp(prefix="doxify_bench_"))
    try:
        print(f"Membuat {args.photos} foto uji (~{args.size_mb:.0f} MB)...")
        photos = []
        for i in range(args.photos):
            p = work / f"foto{i:03d}.jpg"
            make_photo(p, args.size_mb, i)
            photos.append(p)
        avg = sum(p.stat().st_size for p in photos) / len(photos) / 1024 / 1024
        print(f"Rata-rata ukuran foto: {avg:.1f} MB\n")

        print(f"{'kasus':<34} {'jumlah':>10}   {'waktu':>8}   {'ukuran':>12}   memori")
        run_case("asli_gabungan", photos, work, ConversionSettings())
        run_case("terkompres_gabungan", photos, work, ConversionSettings(quality="compressed"))
        run_case("asli_terpisah", photos, work / "terpisah", ConversionSettings(output_mode="separate"))

        extra = [work / f"tambahan{i:03d}.jpg" for i in range(60 - len(photos))]
        for i, p in enumerate(extra):
            shutil.copy(photos[i % len(photos)], p)
        if extra:
            run_case("asli_gabungan_60", photos + extra, work, ConversionSettings())

        if not args.skip_large:
            big = work / "sangat_besar.png"
            Image.effect_noise((10000, 9000), 60).convert("L").save(big)  # 90 megapiksel
            run_case("satu_gambar_90_megapiksel", [big], work, ConversionSettings())
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
