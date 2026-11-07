"""Penghapusan metadata JPEG tanpa kompres ulang (FR-26).

Segmen JPEG yang berisi metadata (EXIF/GPS, XMP, Photoshop, komentar, thumbnail)
dibuang langsung di level byte, sehingga data piksel tidak disentuh sama sekali.
Satu-satunya info EXIF yang dipertahankan adalah Orientation, dalam segmen
minimal, supaya img2pdf tetap bisa memutar halaman dengan benar (FR-30).
"""
from __future__ import annotations

_SOI = 0xD8
_EOI = 0xD9
_SOS = 0xDA
_APP0, _APP1, _APP2, _APP13, _APP14 = 0xE0, 0xE1, 0xE2, 0xED, 0xEE
_COM = 0xFE

# APP yang aman dan perlu dipertahankan: JFIF (APP0), profil warna ICC (APP2),
# Adobe (APP14, penting untuk JPEG CMYK). APP lain dibuang.
_KEEP_APP = {_APP0, _APP2, _APP14}


def build_orientation_segment(orientation: int) -> bytes:
    """Segmen APP1/EXIF minimal yang hanya berisi tag Orientation (0x0112)."""
    if not 1 <= orientation <= 8:
        raise ValueError("Orientation EXIF harus 1-8")
    tiff = (
        b"MM\x00\x2a\x00\x00\x00\x08"  # header TIFF big-endian, IFD0 di offset 8
        + b"\x00\x01"  # jumlah entri: 1
        + b"\x01\x12\x00\x03\x00\x00\x00\x01"  # tag 0x0112, tipe SHORT, count 1
        + orientation.to_bytes(2, "big") + b"\x00\x00"  # nilai + padding
        + b"\x00\x00\x00\x00"  # tidak ada IFD berikutnya
    )
    payload = b"Exif\x00\x00" + tiff
    return b"\xff\xe1" + (len(payload) + 2).to_bytes(2, "big") + payload


def strip_jpeg_metadata(data: bytes, orientation: int = 1) -> bytes:
    """Kembalikan JPEG tanpa metadata. Piksel identik (lossless).

    Raises ValueError jika data bukan JPEG yang utuh (mis. terpotong).
    """
    n = len(data)
    if n < 4 or data[0] != 0xFF or data[1] != _SOI:
        raise ValueError("Bukan file JPEG")

    segments: list[bytes] = []  # segmen sebelum data gambar, sudah disaring
    body = bytearray()  # mulai dari SOS sampai EOI
    pos = 2
    seen_eoi = False

    while pos < n:
        if data[pos] != 0xFF:
            raise ValueError("Struktur JPEG rusak")
        while pos < n and data[pos] == 0xFF:  # buang byte pengisi 0xFF
            pos += 1
        if pos >= n:
            break
        marker = data[pos]
        pos += 1

        if marker == _EOI:
            body += b"\xff\xd9"
            seen_eoi = True
            break
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:  # marker tanpa panjang
            if body:
                body += bytes([0xFF, marker])
            else:
                segments.append(bytes([0xFF, marker]))
            continue

        if pos + 2 > n:
            raise ValueError("JPEG terpotong")
        length = int.from_bytes(data[pos:pos + 2], "big")
        if length < 2 or pos + length > n:
            raise ValueError("JPEG terpotong")
        seg = bytes([0xFF, marker]) + data[pos:pos + length]
        pos += length

        if marker == _SOS:
            body += seg
            # salin data entropi sampai marker non-RST berikutnya
            start = pos
            while True:
                idx = data.find(b"\xff", pos)
                if idx == -1 or idx + 1 >= n:
                    raise ValueError("JPEG terpotong")
                nxt = data[idx + 1]
                if nxt == 0x00 or 0xD0 <= nxt <= 0xD7 or nxt == 0xFF:
                    pos = idx + 1 if nxt == 0xFF else idx + 2
                    continue
                break
            body += data[start:idx]
            pos = idx
            continue

        if body:  # segmen di antara scan (progressive): salin apa adanya
            body += seg
        elif 0xE0 <= marker <= 0xEF:
            if marker in _KEEP_APP:
                segments.append(seg)
        elif marker == _COM:
            continue
        else:
            segments.append(seg)

    if not seen_eoi:
        raise ValueError("JPEG terpotong (tanpa penanda akhir)")

    head = [b"\xff\xd8"]
    orient = build_orientation_segment(orientation) if orientation != 1 else b""
    placed = False
    for seg in segments:
        head.append(seg)
        if not placed and seg[1] == _APP0:
            head.append(orient)  # letakkan setelah JFIF agar urutan tetap wajar
            placed = True
    if not placed:
        head.insert(1, orient)
    return b"".join(head) + bytes(body)
