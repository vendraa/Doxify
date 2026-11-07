"""Skrip uji sederhana untuk inti konversi (sebelum GUI ada).

Contoh:
    python -m app.cli foto1.jpg foto2.png -o hasil.pdf
    python -m app.cli *.jpg -o hasil_folder --separate --page original --margin none
"""
from __future__ import annotations

import argparse
import sys

from app.converters import CancelToken, ConversionSettings, ImageConverter
from app.utils.temp import cleanup_stale_temp_dirs


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="doxify", description="Konversi JPG/PNG ke PDF, 100% offline.")
    p.add_argument("files", nargs="+", help="file gambar (.jpg, .jpeg, .png), urutan = urutan halaman")
    p.add_argument("-o", "--output", required=True, help="file PDF tujuan (mode gabungan) atau folder (--separate)")
    p.add_argument("--separate", action="store_true", help="satu PDF per gambar")
    p.add_argument("--page", choices=["a4", "letter", "original"], default="a4")
    p.add_argument("--orientation", choices=["auto", "portrait", "landscape"], default="auto")
    p.add_argument("--margin", choices=["none", "small", "medium"], default="small")
    p.add_argument("--quality", choices=["original", "compressed"], default="original")
    p.add_argument("--jpeg-quality", type=int, default=75, help="1-95, hanya untuk --quality compressed")
    p.add_argument("--keep-metadata", action="store_true", help="jangan hapus EXIF/GPS dari JPG")
    p.add_argument("--overwrite", action="store_true", help="timpa file tujuan jika sudah ada")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        settings = ConversionSettings(
            page_size=args.page,
            orientation=args.orientation,
            margin=args.margin,
            quality=args.quality,
            jpeg_quality=args.jpeg_quality,
            strip_metadata=not args.keep_metadata,
            output_mode="separate" if args.separate else "merged",
            overwrite=args.overwrite,
        )
    except ValueError as exc:
        print(f"Pengaturan tidak valid: {exc}", file=sys.stderr)
        return 2

    cleanup_stale_temp_dirs()

    def progress(step: int, total: int, label: str) -> None:
        print(f"[{step}/{total}] {label}")

    token = CancelToken()
    try:
        result = ImageConverter().convert(args.files, args.output, settings, progress, token)
    except KeyboardInterrupt:
        token.cancel()
        print("Dibatalkan.", file=sys.stderr)
        return 130
    except Exception as exc:  # DoxifyError dan kegagalan tak terduga
        print(f"Gagal: {exc}", file=sys.stderr)
        return 1

    for out in result.outputs:
        print(f"PDF dibuat: {out}")
    for failed in result.failed:
        print(f"DILEWATI: {failed.path.name} - {failed.reason}", file=sys.stderr)
    print(f"Berhasil: {len(result.converted)}, dilewati: {len(result.failed)}")
    return 0 if result.outputs else 1


if __name__ == "__main__":
    raise SystemExit(main())
