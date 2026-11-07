"""Converter gambar JPG/JPEG/PNG -> PDF (Fase 1, tanpa GUI)."""
from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import img2pdf
from PIL import Image, ImageOps, UnidentifiedImageError

from app.converters.base import (
    BaseConverter,
    CancelToken,
    ConversionCancelled,
    ConversionResult,
    ConversionSettings,
    DoxifyError,
    FailedFile,
    InvalidImageError,
    Margin,
    Orientation,
    OutputError,
    OutputMode,
    PageSize,
    ProgressCallback,
    Quality,
)
from app.utils.filenames import build_pdf_path, unique_path
from app.utils.metadata import strip_jpeg_metadata
from app.utils.temp import SessionTempDir

log = logging.getLogger(__name__)

# Batas ukuran dijaga sendiri (di bawah), jadi peringatan bawaan Pillow dimatikan.
Image.MAX_IMAGE_PIXELS = None

SUPPORTED_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png"})
MAX_PIXELS = 150_000_000  # ~150 megapiksel per gambar (NFR-05)
MAX_TOTAL_BYTES = 1_500_000_000  # batas data gambar per satu PDF gabungan
_EXIF_ORIENTATION = 0x0112
_MARGIN_MM = {Margin.NONE: 0.0, Margin.SMALL: 10.0, Margin.MEDIUM: 20.0}
_PRODUCER = "Doxify"


@dataclass(frozen=True)
class ImageInfo:
    path: Path
    format: str  # "JPEG" atau "PNG" (dari isi file, bukan ekstensi)
    width: int
    height: int
    mode: str
    orientation: int  # 1-8
    has_alpha: bool


def inspect_image(path: str | Path) -> ImageInfo:
    """Validasi isi file (FR-03, FR-04) dan baca info dasarnya.

    Gambar di-decode penuh sekali di sini supaya file terpotong/rusak ketahuan
    sebelum masuk ke PDF.
    """
    path = Path(path)
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        shown = path.suffix or "(tanpa ekstensi)"
        raise InvalidImageError(f"Format {shown} tidak didukung. Gunakan JPG atau PNG.")
    if not path.is_file():
        raise InvalidImageError("File tidak ditemukan (mungkin sudah dipindah atau dihapus).")
    try:
        with Image.open(path) as img:
            fmt = img.format
            if fmt not in ("JPEG", "PNG"):
                raise InvalidImageError("Isi file bukan JPG atau PNG yang valid.")
            width, height = img.size
            if width * height > MAX_PIXELS:
                mp = width * height / 1_000_000
                raise InvalidImageError(
                    f"Gambar terlalu besar ({mp:.0f} megapiksel). Batasnya {MAX_PIXELS // 1_000_000} megapiksel."
                )
            img.load()
            orientation = img.getexif().get(_EXIF_ORIENTATION, 1)
            if orientation not in range(1, 9):
                orientation = 1  # nilai tidak valid (mis. 0 dari beberapa ponsel) diabaikan
            has_alpha = img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info
            return ImageInfo(path, fmt, width, height, img.mode, orientation, has_alpha)
    except InvalidImageError:
        raise
    except PermissionError as exc:
        raise InvalidImageError("Tidak punya izin untuk membaca file ini.") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError) as exc:
        raise InvalidImageError("File rusak atau bukan gambar yang valid.") from exc


def _to_flat(img: Image.Image) -> Image.Image:
    """Terapkan rotasi EXIF, ratakan transparansi ke latar putih (FR-30, FR-31)."""
    img = ImageOps.exif_transpose(img)
    if img.mode in ("I;16", "I;16B", "I;16L", "I"):
        img = img.point(lambda v: v / 256).convert("L")
    has_alpha = img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info
    if has_alpha:
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    if img.mode in ("L", "RGB"):
        return img
    return img.convert("RGB")


def _layout_fun(settings: ConversionSettings):
    """Susun ukuran halaman, orientasi, dan margin untuk img2pdf (FR-21..FR-24)."""
    margin_pt = img2pdf.mm_to_pt(_MARGIN_MM[settings.margin])
    border = (margin_pt, margin_pt) if margin_pt else None

    if settings.page_size is PageSize.ORIGINAL:
        pagesize = None  # halaman = ukuran gambar; orientasi tidak relevan
        auto_orient = False
    else:
        if settings.page_size is PageSize.A4:
            width, height = img2pdf.mm_to_pt(210), img2pdf.mm_to_pt(297)
        else:
            width, height = img2pdf.in_to_pt(8.5), img2pdf.in_to_pt(11)
        if settings.orientation is Orientation.LANDSCAPE:
            width, height = height, width
        pagesize = (width, height)
        auto_orient = settings.orientation is Orientation.AUTO

    return img2pdf.get_layout_fun(pagesize, None, border, img2pdf.FitMode.into, auto_orient)


def _write_atomic(dest: Path, data: bytes) -> None:
    """Tulis lewat file sementara lalu rename, supaya tidak ada PDF setengah jadi."""
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=dest.parent, prefix=".doxify-", suffix=".tmp")
    except OSError as exc:
        raise OutputError(f"Tidak bisa menulis ke folder tujuan: {exc.strerror or exc}") from exc
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp_name, dest)
    except PermissionError as exc:
        _silent_unlink(tmp_name)
        raise OutputError("File tujuan sedang dipakai aplikasi lain atau tidak ada izin menulis.") from exc
    except OSError as exc:
        _silent_unlink(tmp_name)
        raise OutputError(f"Gagal menyimpan PDF: {exc.strerror or exc}") from exc
    except BaseException:
        _silent_unlink(tmp_name)
        raise


def _silent_unlink(name: str) -> None:
    try:
        os.unlink(name)
    except OSError:
        pass


class ImageConverter(BaseConverter):
    """JPG/JPEG/PNG -> PDF.

    `output`:
      - mode MERGED   : path file PDF tujuan (nama dibersihkan otomatis).
      - mode SEPARATE : folder tujuan; satu PDF per gambar, bernama sesuai gambarnya.
    """

    extensions = SUPPORTED_EXTENSIONS

    # ---- API publik -------------------------------------------------------

    def convert(
        self,
        inputs: Iterable[str | Path],
        output: str | Path,
        settings: ConversionSettings | None = None,
        progress: ProgressCallback | None = None,
        cancel: CancelToken | None = None,
    ) -> ConversionResult:
        settings = settings or ConversionSettings()
        paths = [Path(p) for p in inputs]
        if not paths:
            raise DoxifyError("Tidak ada file untuk dikonversi.")
        cancel = cancel or CancelToken()
        result = ConversionResult()

        with SessionTempDir() as workdir:
            try:
                if settings.output_mode is OutputMode.MERGED:
                    self._convert_merged(paths, Path(output), settings, progress, cancel, workdir, result)
                else:
                    self._convert_separate(paths, Path(output), settings, progress, cancel, workdir, result)
            except ConversionCancelled:
                result.cancelled = True
        return result

    # ---- mode gabungan / terpisah ----------------------------------------

    def _convert_merged(self, paths, output, settings, progress, cancel, workdir, result) -> None:
        total = len(paths) + 1
        ready: list[tuple[Path, Path]] = []
        for index, path in enumerate(paths):
            cancel.raise_if_cancelled()
            _report(progress, index, total, path.name)
            prepared = self._prepare_one(path, index, settings, workdir, result)
            if prepared is not None:
                ready.append((path, prepared))

        if not ready:
            return
        if sum(p.stat().st_size for _, p in ready) > MAX_TOTAL_BYTES:
            raise DoxifyError(
                "Total ukuran gambar terlalu besar untuk satu PDF. Bagi menjadi beberapa PDF yang lebih kecil."
            )

        cancel.raise_if_cancelled()
        _report(progress, len(paths), total, "Menyusun PDF")
        pdf_bytes, good = self._assemble(ready, settings, result)
        if pdf_bytes is None:
            return

        cancel.raise_if_cancelled()
        dest = self._resolve_output(output, settings)
        _write_atomic(dest, pdf_bytes)
        result.outputs.append(dest)
        result.converted.extend(orig for orig, _ in good)
        _report(progress, total, total, "Selesai")

    def _convert_separate(self, paths, out_dir, settings, progress, cancel, workdir, result) -> None:
        total = len(paths)
        for index, path in enumerate(paths):
            cancel.raise_if_cancelled()
            _report(progress, index, total, path.name)
            prepared = self._prepare_one(path, index, settings, workdir, result)
            if prepared is None:
                continue
            pdf_bytes, good = self._assemble([(path, prepared)], settings, result)
            if pdf_bytes is None:
                continue
            cancel.raise_if_cancelled()
            dest = self._resolve_output(out_dir / path.stem, settings)
            _write_atomic(dest, pdf_bytes)
            result.outputs.append(dest)
            result.converted.append(path)
        _report(progress, total, total, "Selesai")

    # ---- langkah per gambar ----------------------------------------------

    def _prepare_one(self, path, index, settings, workdir, result) -> Path | None:
        """Validasi + siapkan satu gambar. Kegagalan dicatat, tidak menghentikan batch (FR-34)."""
        try:
            info = inspect_image(path)
            return self._prepare(info, index, settings, workdir)
        except DoxifyError as exc:
            result.failed.append(FailedFile(path, str(exc)))
        except (OSError, ValueError) as exc:
            result.failed.append(FailedFile(path, f"Gagal memproses gambar: {_short(exc)}"))
        return None

    def _prepare(self, info: ImageInfo, index: int, settings: ConversionSettings, workdir: Path) -> Path:
        """Kembalikan path gambar yang siap dimasukkan ke PDF.

        Prinsip: JPG tidak dikompres ulang selama tidak terpaksa (kualitas asli).
        """
        if settings.quality is Quality.COMPRESSED:
            return self._save_compressed(info, index, settings, workdir)

        mirrored = info.orientation in (2, 4, 5, 7)  # tidak bisa diwakili rotasi halaman PDF

        if info.format == "JPEG":
            if mirrored:
                return self._save_flat(info, index, workdir, as_jpeg=True)
            if settings.strip_metadata:
                try:
                    data = strip_jpeg_metadata(info.path.read_bytes(), info.orientation)
                except ValueError as exc:
                    raise InvalidImageError("File JPG rusak atau terpotong.") from exc
                out = workdir / f"{index:05d}.jpg"
                out.write_bytes(data)
                return out
            return info.path

        # PNG: lolos langsung jika tidak butuh diratakan.
        simple_mode = info.mode in ("RGB", "L", "P", "1")
        if simple_mode and not info.has_alpha and not mirrored:
            return info.path
        return self._save_flat(info, index, workdir, as_jpeg=False)

    def _save_flat(self, info: ImageInfo, index: int, workdir: Path, as_jpeg: bool) -> Path:
        with Image.open(info.path) as img:
            flat = _to_flat(img)
            if as_jpeg:  # hanya untuk JPG cermin yang jarang; kualitas tinggi
                out = workdir / f"{index:05d}.jpg"
                flat.save(out, "JPEG", quality=95, subsampling=0)
            else:
                out = workdir / f"{index:05d}.png"
                flat.save(out, "PNG")
        return out

    def _save_compressed(self, info: ImageInfo, index: int, settings: ConversionSettings, workdir: Path) -> Path:
        with Image.open(info.path) as img:
            flat = _to_flat(img)
            if settings.max_long_edge and max(flat.size) > settings.max_long_edge:
                flat.thumbnail((settings.max_long_edge, settings.max_long_edge), Image.Resampling.LANCZOS)
            out = workdir / f"{index:05d}.jpg"
            flat.save(out, "JPEG", quality=settings.jpeg_quality, optimize=True)
        return out

    # ---- perakitan PDF ----------------------------------------------------

    def _assemble(self, items, settings, result):
        """Rakit PDF. Jika gagal, cari gambar bermasalah, lewati, lalu coba lagi."""
        layout = _layout_fun(settings)

        def build(paths: list[Path]) -> bytes:
            return img2pdf.convert(
                paths,
                layout_fun=layout,
                rotation=img2pdf.Rotation.ifvalid,
                producer=_PRODUCER,
                creator=_PRODUCER,
            )

        try:
            return build([prep for _, prep in items]), items
        except Exception:  # noqa: BLE001 - kegagalan library apa pun ditangani di bawah
            log.debug("Perakitan gabungan gagal, memeriksa satu per satu", exc_info=True)

        good = []
        for orig, prep in items:
            try:
                build([prep])
                good.append((orig, prep))
            except Exception as exc:  # noqa: BLE001
                result.failed.append(FailedFile(orig, f"Gagal dimasukkan ke PDF: {_short(exc)}"))
        if not good:
            return None, []
        try:
            return build([prep for _, prep in good]), good
        except Exception as exc:  # noqa: BLE001
            raise DoxifyError(f"Gagal menyusun PDF: {_short(exc)}") from exc

    def _resolve_output(self, target: Path, settings: ConversionSettings) -> Path:
        try:
            dest = build_pdf_path(target.parent, target.name)
            return dest if settings.overwrite else unique_path(dest)
        except ValueError as exc:
            raise OutputError(str(exc)) from exc


def _report(progress: ProgressCallback | None, step: int, total: int, label: str) -> None:
    if progress is not None:
        progress(step, total, label)


def _short(exc: BaseException) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    return text if len(text) <= 120 else text[:117] + "..."
