"""Membuat assets/doxify.ico (ikon aplikasi, FR-55). Dijalankan sekali; hasilnya ikut disimpan di repo.

    python scripts/make_icon.py
Desain: lembar putih berlipat sudut di atas lembar kedua (isyarat 'menggabung'), pita merah di bawah
(isyarat PDF), di atas kotak biru membulat. Hanya bentuk, tanpa teks, supaya tetap jelas di 16 px.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
CANVAS = 1024


def draw_icon() -> Image.Image:
    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))

    # latar biru dengan gradasi vertikal, dipotong ke persegi membulat
    gradient = Image.new("RGBA", (CANVAS, CANVAS))
    gd = ImageDraw.Draw(gradient)
    top, bottom = (59, 130, 246), (30, 64, 175)
    for y in range(CANVAS):
        t = y / (CANVAS - 1)
        gd.line([(0, y), (CANVAS, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)) + (255,))
    mask = Image.new("L", (CANVAS, CANVAS), 0)
    ImageDraw.Draw(mask).rounded_rectangle([40, 40, CANVAS - 40, CANVAS - 40], radius=210, fill=255)
    img.paste(gradient, (0, 0), mask)

    d = ImageDraw.Draw(img)
    # lembar belakang
    d.rounded_rectangle([215, 215, 705, 905], radius=40, fill=(186, 209, 247, 255))
    # lembar depan dengan sudut atas kanan terlipat
    page = [(290, 150), (640, 150), (800, 310), (800, 880), (290, 880)]
    d.polygon(page, fill=(255, 255, 255, 255))
    d.polygon([(640, 150), (640, 310), (800, 310)], fill=(205, 219, 240, 255))
    # garis teks
    for y, x2 in ((420, 720), (520, 720), (620, 600)):
        d.rounded_rectangle([370, y, x2, y + 44], radius=22, fill=(148, 163, 189, 255))
    # pita merah (PDF) dengan tanda panah ke bawah
    d.rectangle([290, 720, 800, 880], fill=(220, 38, 38, 255))
    d.polygon([(480, 755), (610, 755), (545, 845)], fill=(255, 255, 255, 255))
    return img


def main() -> int:
    out = Path(__file__).resolve().parent.parent / "assets" / "doxify.ico"
    out.parent.mkdir(exist_ok=True)
    draw_icon().resize((256, 256), Image.Resampling.LANCZOS).save(out, format="ICO", sizes=SIZES)
    print(f"Ikon dibuat: {out} ({out.stat().st_size} byte)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
