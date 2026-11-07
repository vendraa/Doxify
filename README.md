# Doxify (Fase 1: inti konversi)

Konversi JPG/PNG ke PDF, 100% offline. Fase ini belum punya GUI; diuji lewat CLI dan tes otomatis.

## Menjalankan di Windows (PowerShell)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# uji
python -m unittest discover -s tests -t .      # atau: pytest

# pakai
python -m app.cli foto1.jpg foto2.png -o hasil.pdf
python -m app.cli *.jpg -o folder_hasil --separate --page original --margin none
python -m app.cli scan.jpg -o kecil.pdf --quality compressed --jpeg-quality 60
python -m app.cli --help
```

## Struktur

- `app/converters/base.py`   pengaturan, hasil, error, antarmuka converter
- `app/converters/image.py`  validasi + konversi JPG/PNG
- `app/utils/metadata.py`    hapus EXIF/GPS dari JPG tanpa kompres ulang
- `app/utils/filenames.py`   nama file aman Windows, anti-timpa
- `app/utils/temp.py`        folder temp acak, selalu dibersihkan
- `app/cli.py`               skrip uji sebelum GUI
- `tests/`                   tes otomatis

Modul `converters/` dan `utils/` tidak mengimpor apa pun dari `ui/` (NFR-08), dan
satu tes memastikan kode aplikasi tidak mengimpor library jaringan (NFR-01).
