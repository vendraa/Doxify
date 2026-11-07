# Doxify (Fase 1 + 2: inti konversi dan GUI)

Konversi JPG/PNG ke PDF, 100% offline. Bisa dipakai lewat aplikasi desktop (GUI) atau CLI.

## Menjalankan di Windows (PowerShell)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt

# jalankan aplikasi (GUI)
python -m app.main
python -m app.main foto1.jpg foto2.png          # langsung membuka dengan file

# uji (tes GUI memakai Qt 'offscreen', tidak memunculkan jendela)
python -m unittest discover -s tests -t .      # atau: pytest

# pakai lewat CLI
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
- `app/ui/logic.py`          logika daftar file, ringkasan hasil (tanpa Qt, diuji penuh)
- `app/ui/file_list.py`      daftar drag-and-drop + thumbnail
- `app/ui/worker.py`         konversi di thread terpisah
- `app/ui/main_window.py`    jendela utama
- `app/main.py`              titik masuk aplikasi
- `app/utils/settings_store.py` pengaturan tersimpan lokal (%APPDATA%\Doxify)
- `app/cli.py`               alternatif command line
- `tests/`                   tes otomatis

Modul `converters/` dan `utils/` tidak mengimpor apa pun dari `ui/` atau Qt (NFR-08), dan
satu tes memastikan kode aplikasi tidak mengimpor library jaringan (NFR-01).
