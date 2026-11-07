"""Pembuat gambar uji + pembaca isi PDF."""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image
from pypdf import PdfReader


def make_jpeg(path: Path, size=(200, 100), color=(200, 30, 30), orientation=None,
              with_exif=False, mode="RGB", quality=90) -> Path:
    img = Image.new(mode, size, color if mode == "RGB" else (10, 20, 30, 40) if mode == "CMYK" else 128)
    kwargs = {"quality": quality}
    if orientation is not None or with_exif:
        exif = Image.Exif()
        if orientation is not None:
            exif[0x0112] = orientation
        if with_exif:
            exif[0x010F] = "TestCam"
            exif[0x0131] = "RahasiaSoftware"
            exif[0x8825] = {1: "S", 2: (6.0, 59.0, 0.0), 3: "E", 4: (110.0, 24.0, 0.0)}
        kwargs["exif"] = exif
    img.save(path, "JPEG", **kwargs)
    return path


def make_png(path: Path, size=(120, 80), color=(10, 120, 200, 255), mode="RGBA", **save_kw) -> Path:
    img = Image.new(mode, size, color if mode == "RGBA" else color[:3] if mode == "RGB" else color[0])
    img.save(path, "PNG", **save_kw)
    return path


def page_dims(reader: PdfReader, i: int = 0) -> tuple[float, float]:
    """Ukuran halaman efektif (memperhitungkan /Rotate)."""
    page = reader.pages[i]
    w, h = float(page.mediabox.width), float(page.mediabox.height)
    if page.rotation % 180 == 90:
        w, h = h, w
    return w, h


def embedded_image_bytes(reader: PdfReader, i: int = 0) -> bytes:
    """Stream gambar mentah di dalam PDF (untuk JPEG = DCTDecode apa adanya).

    Sengaja tidak memakai page.images[i].data: pypdf menyimpan ulang gambar lewat
    Pillow sehingga byte-nya berubah dan tidak mencerminkan isi PDF sebenarnya.
    """
    xobjects = reader.pages[i]["/Resources"]["/XObject"]
    stream = list(xobjects.values())[0].get_object()
    return stream.get_data()


def embedded_pil(reader: PdfReader, i: int = 0) -> Image.Image:
    return reader.pages[i].images[0].image
