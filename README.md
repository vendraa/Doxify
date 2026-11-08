# Doxify (Fase 1-4: inti konversi, GUI, hardening, pengemasan)

Konversi JPG/PNG ke PDF, 100% offline. Bisa dipakai lewat aplikasi desktop (GUI) atau CLI.

## Menjalankan di Windows (PowerShell)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

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

## Fase 3: verifikasi keamanan dan ketahanan

Tes otomatis (jalan di mana saja, tanpa internet):

```powershell
python -m unittest discover -s tests -t .
```

Yang dibuktikan tes tersebut: jaringan diblokir tapi konversi tetap berhasil (di dalam proses dan di
proses terpisah), kode tidak berisi URL/telemetri, log dan konsol tidak memuat nama file, file rusak
tidak membuat crash atau hang (fuzzing), disk penuh dan PDF yang sedang dibuka aplikasi lain ditangani
dengan pesan jelas tanpa merusak PDF lama, pembatalan tidak meninggalkan file, dan sisa temp akibat
proses yang di-kill dibersihkan saat aplikasi dibuka lagi.

Hal yang HANYA bisa dibuktikan di Windows (jalankan PowerShell sebagai Administrator, virtualenv aktif):

```powershell
# 1. Uji offline nyata dengan Windows Firewall: memblokir Python, memastikan blokirnya efektif,
#    menjalankan semua tes + konversi nyata, lalu menghapus aturan firewall
.\scripts\windows\verify-offline.ps1

# 2. Mencoba GUI secara manual saat jaringan diblokir
.\scripts\windows\block-network.ps1 -Action Add
python -m app.main
.\scripts\windows\block-network.ps1 -Action Remove      # jangan lupa

# 3. Audit kerentanan library (butuh internet; hanya di komputer pengembangan)
.\scripts\windows\audit-dependencies.ps1

# 4. Kecepatan dan memori di laptopmu (NFR-03/04/05)
python scripts\benchmark.py
```

Skrip PowerShell ditulis tanpa bisa dijalankan di lingkungan pengembangan (tidak ada Windows di sana),
jadi jalankan dulu dan laporkan jika ada error.

## Fase 4: membangun installer

Prasyarat di komputer pembuat (butuh internet hanya untuk memasang alat build, bukan untuk aplikasinya):
virtualenv proyek aktif dengan `pip install -r requirements.txt`, dan **Inno Setup 6.3 atau lebih baru**
(https://jrsoftware.org/isinfo.php) untuk langkah installer.

```powershell
.\scripts\windows\build.ps1                  # tes -> PyInstaller -> periksa isi paket -> uji mandiri -> ZIP -> installer -> hash
.\scripts\windows\build.ps1 -SkipInstaller   # tanpa Inno Setup (hanya folder dan ZIP portabel)
```

Hasil di folder `dist\`: `Doxify\` (folder aplikasi), `Doxify-Portable-<versi>.zip`,
`installer\Doxify-Setup-<versi>.exe`, `SHA256SUMS.txt`, dan `build-info.txt` (versi semua library saat build).
Build berhenti di langkah yang gagal. Dua pemeriksaan otomatis di dalamnya:

- `scripts\verify_build.py`: gagal jika Qt Network atau SSL ikut terbungkus, atau plugin Qt wajib hilang.
- `Doxify.exe --self-test laporan.txt`: konversi nyata, jendela utama, plugin gambar Qt, dan pemantau
  jaringan (setiap upaya koneksi digagalkan dan dilaporkan) dijalankan DARI DALAM paket hasil build.
  Kode keluar 0 = lulus. Bisa juga dijalankan sendiri kapan saja, termasuk pada aplikasi yang sudah terpasang.

Menaikkan versi: ubah `__version__` di `app\__init__.py` dan nilai bawaan `#define AppVersion` di
`installer\setup.iss` (sebuah tes memastikan keduanya sama). `AppId` di `setup.iss` jangan pernah diubah.

### Uji pasang/hapus (manual, di Windows bersih)

Paling aman memakai Windows Sandbox (Windows 10/11 Pro; aktifkan di "Turn Windows features on or off"):

1. Salin `Doxify-Setup-<versi>.exe` ke Sandbox lalu jalankan. Tidak boleh ada prompt UAC (minta izin admin).
2. Aplikasi terpasang di `%LOCALAPPDATA%\Programs\Doxify`, shortcut Start Menu muncul, shortcut Desktop hanya
   jika kotaknya dicentang.
3. Buka Doxify, konversi beberapa gambar, simpan PDF.
4. Jalankan installer lagi (versi sama, lalu versi yang lebih baru): harus menjadi pembaruan, tanpa entri
   ganda di Settings > Apps.
5. Uninstall dari Settings > Apps: folder aplikasi hilang, sisa `doxify_*` di folder temp hilang, ada
   pertanyaan apakah pengaturan ikut dihapus (bawaan "Tidak"), dan gambar serta PDF Anda utuh.

### Peringatan yang wajar muncul

Installer dan `.exe` tidak ditandatangani secara digital. Windows SmartScreen bisa menampilkan
"Windows protected your PC": klik **More info > Run anyway**. Windows Defender kadang menandai hasil
PyInstaller sebagai mencurigakan (false positive); untuk pemakaian pribadi tambahkan pengecualian untuk folder
instalasi. Cocokkan hash installer dengan `SHA256SUMS.txt` jika ingin memastikan file tidak berubah.

### Yang BELUM terbukti

Skrip build, `build.spec`, dan `setup.iss` belum pernah dijalankan, karena PyInstaller, Inno Setup, dan
Windows tidak tersedia di lingkungan pengembangan. Yang sudah diuji: pembuat ikon dan info versi,
pemeriksa isi paket, uji mandiri, struktur dan aturan keamanan pada `setup.iss` dan `build.spec`, dan bukti bahwa
inti aplikasi tetap berjalan tanpa modul yang dikecualikan dari paket.
