"""Memeriksa isi folder hasil build (dist/Doxify) sebelum dibungkus installer.

    python scripts/verify_build.py dist/Doxify
Kode keluar 1 jika ada ERROR. PERINGATAN tidak menggagalkan, tapi perlu dibaca.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

EXE_NAME = "Doxify.exe"

# Binary yang membuktikan ada kemampuan jaringan "tersembunyi" di dalam paket.
FORBIDDEN = {
    "qt6network.dll": "modul jaringan Qt ikut terbungkus (QtNetwork seharusnya dikecualikan)",
    "_ssl.pyd": "modul SSL Python ikut terbungkus (ssl seharusnya dikecualikan)",
}
# Tidak selalu berbahaya (mis. dibawa library lain), jadi hanya peringatan.
SUSPICIOUS_PREFIXES = {
    "libssl": "pustaka SSL ada di paket",
    "libcrypto": "pustaka kripto OpenSSL ada di paket",
    "_socket.pyd": "modul socket ada di paket (wajar bila dibawa library lain)",
}
REQUIRED = {
    "qwindows.dll": "plugin platform Qt untuk Windows (tanpa ini aplikasi tidak bisa membuka jendela)",
    "qjpeg.dll": "plugin gambar JPEG Qt (tanpa ini thumbnail JPG tidak muncul)",
}


@dataclass
class Finding:
    level: str  # "ERROR" | "PERINGATAN" | "INFO"
    message: str


def verify(dist: Path) -> list[Finding]:
    dist = Path(dist)
    findings: list[Finding] = []
    if not dist.is_dir():
        return [Finding("ERROR", f"Folder tidak ditemukan: {dist}")]
    if not (dist / EXE_NAME).is_file():
        findings.append(Finding("ERROR", f"{EXE_NAME} tidak ada di {dist}"))

    files = [p for p in dist.rglob("*") if p.is_file()]
    names = {p.name.lower(): p for p in files}

    for name, why in FORBIDDEN.items():
        if name in names:
            findings.append(Finding("ERROR", f"{names[name].name}: {why}"))
    for prefix, why in SUSPICIOUS_PREFIXES.items():
        hits = [p.name for p in files if p.name.lower().startswith(prefix)]
        if hits:
            findings.append(Finding("PERINGATAN", f"{', '.join(sorted(hits)[:3])}: {why}"))
    for name, why in REQUIRED.items():
        if name not in names:
            findings.append(Finding("ERROR", f"{name} tidak ada: {why}"))

    leaked = [p for p in files if p.name.lower() in {"settings.json"} or p.name.startswith("test_")]
    for p in leaked[:5]:
        findings.append(Finding("ERROR", f"file yang tidak boleh ikut terbungkus: {p.relative_to(dist)}"))

    total_mb = sum(p.stat().st_size for p in files) / 1024 / 1024
    findings.append(Finding("INFO", f"{len(files)} file, total {total_mb:.0f} MB"))
    return findings


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Pemakaian: python scripts/verify_build.py dist/Doxify", file=sys.stderr)
        return 2
    findings = verify(Path(argv[1]))
    for f in findings:
        print(f"[{f.level}] {f.message}")
    errors = [f for f in findings if f.level == "ERROR"]
    print("\nHASIL: " + ("GAGAL" if errors else "LULUS"))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
