# Doxify

**Konverter JPG/PNG ke PDF untuk Windows yang berjalan 100% di komputermu sendiri.**
Tanpa upload, tanpa akun, tanpa koneksi internet.

![Python 3.14](https://img.shields.io/badge/python-3.14-blue)
![Platform Windows 10/11](https://img.shields.io/badge/platform-Windows%2010%2F11-informational)
![Offline](https://img.shields.io/badge/jaringan-tidak%20dipakai-success)
![Versi 1.0.0](https://img.shields.io/badge/versi-1.0.0-lightgrey)

---

## Daftar Isi

1. [Tentang Doxify](#tentang-doxify)
2. [Fitur](#fitur)
3. [Tech Stack](#tech-stack)
4. [Instalasi](#instalasi)
5. [Penggunaan](#penggunaan)
6. [Pengaturan](#pengaturan)
7. [Keamanan dan Privasi](#keamanan-dan-privasi)
8. [Cara Kerja dan Batasan Teknis](#cara-kerja-dan-batasan-teknis)
9. [Arsitektur dan Struktur Proyek](#arsitektur-dan-struktur-proyek)
10. [Pengembangan](#pengembangan)
11. [Membangun Installer (Rilis)](#membangun-installer-rilis)
12. [Pemecahan Masalah](#pemecahan-masalah)
13. [Roadmap](#roadmap)
14. [Lisensi dan Kredit](#lisensi-dan-kredit)

---

## Tentang Doxify

Layanan konversi online seperti ILovePDF praktis, tetapi setiap file harus diunggah ke server pihak lain.
Untuk dokumen sensitif seperti KTP, ijazah, bukti transfer, atau kontrak, itu risiko yang tidak perlu:
mengubah gambar menjadi PDF sebenarnya tidak membutuhkan server sama sekali.

Doxify dibuat dengan satu prinsip utama, **local-first**:

- Semua proses konversi terjadi di komputermu.
- Aplikasi tidak memiliki kode untuk mengakses jaringan, tidak ada telemetri, dan tidak ada pengecek pembaruan.
- File sementara disimpan di folder acak dan dihapus otomatis setelah selesai, dibatalkan, atau jika aplikasi ditutup paksa (dibersihkan saat dibuka kembali).
- Gambar aslimu tidak pernah diubah atau dihapus.

Versi 1.0 fokus pada satu hal dan mengerjakannya dengan baik: **JPG dan PNG menjadi PDF**.

## Fitur

### Input dan daftar file

| Fitur | Keterangan |
|---|---|
| Drag-and-drop | Seret file atau folder dari File Explorer langsung ke jendela |
| Tombol Tambah File | Dialog pilih file dengan multi-select (`Ctrl+O`) |
| Folder | Folder yang dijatuhkan diperluas satu tingkat (tidak rekursif), diurutkan alami: `foto2` sebelum `foto10` |
| Thumbnail | Pratinjau kecil tiap gambar, dimuat di latar belakang sehingga jendela tidak membeku |
| Urutan halaman | Ubah urutan dengan drag, atau tombol Naik/Turun. Urutan daftar = urutan halaman PDF |
| Hapus | Hapus terpilih (`Delete`) atau kosongkan seluruh daftar |
| Validasi | Isi file diperiksa, bukan hanya ekstensinya. File palsu, rusak, atau terpotong dilewati dengan alasan yang jelas |
| Duplikat | Gambar yang sama tidak dimasukkan dua kali |

### Konversi

| Fitur | Pilihan |
|---|---|
| Mode output | Satu PDF gabungan, atau satu PDF per gambar |
| Ukuran halaman | A4, Letter, atau ukuran asli gambar |
| Orientasi | Otomatis (mengikuti gambar), potret, atau lanskap |
| Margin | Tanpa margin, kecil (10 mm), sedang (20 mm) |
| Kualitas | **Asli** (JPG tidak dikompres ulang) atau **terkompres** (file lebih kecil) |
| Metadata | Hapus EXIF/GPS dan info kamera dari JPG, aktif secara bawaan |
| Rotasi EXIF | Foto dari ponsel otomatis tampil tegak |
| PNG transparan | Diberi latar putih (tidak berubah menjadi hitam) |
| Progress dan batal | Progress bar dan tombol Batal. Membatalkan tidak meninggalkan file setengah jadi |
| Ringkasan hasil | Daftar yang berhasil dan yang dilewati beserta alasannya, plus tombol Buka Folder |

Satu file yang bermasalah **tidak** menggagalkan seluruh batch. File itu dilewati, sisanya tetap diproses.

### Lainnya

- Pengaturan terakhir diingat antar sesi.
- Antarmuka command line (`app.cli`) untuk penggunaan skrip.
- Uji mandiri bawaan (`--self-test`) untuk memastikan hasil build atau instalasi benar-benar berfungsi.

### Yang sengaja belum ada di v1.0

Format selain JPG/PNG (WEBP, BMP, TIFF), dokumen Office (DOCX, PPTX, XLSX), teks/HTML, fitur manipulasi PDF
(merge PDF, split, kompres PDF, password), OCR, editor gambar, dukungan macOS/Linux, dan pembaruan otomatis.
Lihat [Roadmap](#roadmap).

## Tech Stack

| Lapisan | Teknologi | Peran |
|---|---|---|
| Bahasa | Python 3.14 | Library PDF dan gambar yang matang, kode ringkas |
| GUI | PySide6 (Qt 6) | Drag-and-drop, daftar yang bisa diurutkan, dan threading yang andal |
| Penyusun PDF | `img2pdf` | Menyisipkan JPG ke PDF **tanpa kompres ulang**, sehingga kualitas tetap asli |
| Pemrosesan gambar | `Pillow` | Validasi, rotasi, perataan transparansi, mode terkompres |
| Pengemasan | PyInstaller (mode folder) | Menjadi `Doxify.exe` yang tidak butuh Python terpasang |
| Installer | Inno Setup 6.3+ atau 7 | Pemasangan per-pengguna tanpa hak administrator |
| Pengujian | `unittest` (kompatibel `pytest`), `pypdf` | Tes otomatis |

Catatan: `img2pdf` membawa `pikepdf` (library native) sebagai dependensi, jadi ikut terbungkus di paket rilis.

## Instalasi

### A. Memakai installer (disarankan untuk pemakaian harian)

1. Bangun installer dengan mengikuti [Membangun Installer](#membangun-installer-rilis), atau minta berkas
   `Doxify-Setup-1.0.0.exe` dari orang yang membangunnya.
2. Jalankan installer. Tidak ada permintaan izin administrator karena Doxify dipasang untuk pengguna aktif saja
   di `%LOCALAPPDATA%\Programs\Doxify`.
3. Buka Doxify dari Start Menu. Shortcut Desktop opsional (kotak centang saat instalasi).

**Pembaruan:** jalankan installer versi yang lebih baru di atas yang lama. Pengaturanmu tetap tersimpan.

**Uninstall:** Settings > Apps > Doxify. Folder aplikasi dan sisa file sementara dihapus, lalu kamu ditanya apakah
pengaturan ikut dihapus (bawaan: tidak). Gambar dan PDF milikmu tidak pernah disentuh.

> **Peringatan yang wajar muncul.** Installer dan `.exe` tidak ditandatangani secara digital. Windows SmartScreen
> dapat menampilkan "Windows protected your PC": klik **More info**, lalu **Run anyway**. Windows Defender
> kadang menandai hasil PyInstaller sebagai mencurigakan (false positive). Untuk pemakaian pribadi, tambahkan
> pengecualian untuk folder instalasi. Cocokkan hash installer dengan `SHA256SUMS.txt` bila ingin memastikan
> file tidak berubah.

### B. Versi portabel (tanpa instalasi)

Ekstrak `Doxify-Portable-1.0.0.zip` ke folder mana pun lalu jalankan `Doxify.exe`. Menghapusnya cukup dengan
menghapus folder tersebut (pengaturan ada di `%APPDATA%\Doxify`).

### C. Dari kode sumber (untuk pengembang)

Prasyarat: Windows 10/11 64-bit dan [Python 3.14](https://www.python.org/downloads/) (64-bit).

```powershell
# ambil kode proyek (git clone atau salin foldernya), lalu masuk ke foldernya
cd doxify

py -3.14 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt          # untuk menjalankan
pip install -r requirements-dev.txt      # untuk tes

python -m app.main
```

Jika PowerShell menolak mengaktifkan virtualenv karena kebijakan eksekusi, jalankan sekali:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

`PySide6` dipasang dengan rentang versi (`>=6.7,<7`). Setelah berhasil terpasang, kunci ke versi pastinya agar
build bisa diulang: jalankan `pip freeze | findstr /i pyside`, lalu ganti baris itu di `requirements.txt`.

## Penggunaan

### Antarmuka grafis

1. Buka Doxify.
2. Seret gambar ke jendela, atau klik **Tambah File**.
3. Atur urutan dengan drag (atau Naik/Turun). Hapus gambar yang tidak perlu.
4. Sesuaikan **Pengaturan** di panel kanan bila perlu.
5. Klik **Konversi**, lalu pilih nama file PDF (mode gabungan) atau folder tujuan (mode per gambar).
6. Setelah selesai, klik **Buka Folder** untuk langsung menyorot hasilnya.

| Pintasan | Fungsi |
|---|---|
| `Ctrl+O` | Tambah file |
| `Delete` | Hapus item terpilih |

Jika file PDF dengan nama yang sama sudah ada, Doxify tidak menimpanya diam-diam. Nama diberi akhiran
(`hasil (1).pdf`), kecuali kamu memilih file yang ada di dialog simpan dan mengonfirmasi penimpaan.

### Command line

Berguna untuk skrip dan otomasi:

```powershell
# beberapa gambar menjadi satu PDF
python -m app.cli foto1.jpg foto2.png -o hasil.pdf

# satu PDF per gambar, ukuran asli, tanpa margin
python -m app.cli *.jpg -o folder_hasil --separate --page original --margin none

# kecilkan ukuran file
python -m app.cli scan.jpg -o kecil.pdf --quality compressed --jpeg-quality 60
```

| Opsi | Nilai | Bawaan | Keterangan |
|---|---|---|---|
| `files` | satu atau lebih path | wajib | Urutan = urutan halaman |
| `-o`, `--output` | path | wajib | File PDF (gabungan) atau folder (`--separate`) |
| `--separate` | | gabungan | Satu PDF per gambar |
| `--page` | `a4`, `letter`, `original` | `a4` | Ukuran halaman |
| `--orientation` | `auto`, `portrait`, `landscape` | `auto` | Tidak berlaku untuk `--page original` |
| `--margin` | `none`, `small`, `medium` | `small` | 0, 10, 20 mm |
| `--quality` | `original`, `compressed` | `original` | |
| `--jpeg-quality` | 1-95 | `75` | Hanya untuk `--quality compressed` |
| `--keep-metadata` | | hapus | Pertahankan EXIF/GPS pada JPG |
| `--overwrite` | | tidak menimpa | Timpa file tujuan jika sudah ada |

Kode keluar `0` berarti ada PDF yang dihasilkan, `1` berarti tidak ada atau terjadi kegagalan, `2` berarti
pengaturan tidak valid.

### Uji mandiri

Memastikan aplikasi benar-benar berfungsi pada mesin tempat ia terpasang, termasuk memeriksa bahwa tidak ada
upaya koneksi jaringan:

```powershell
Doxify.exe --self-test laporan.txt          # lengkap, termasuk memeriksa jendela utama dan plugin Qt
Doxify.exe --self-test --no-gui laporan.txt # tanpa pemeriksaan Qt
```

Laporan ditulis ke `laporan.txt`. Kode keluar `0` berarti semua pemeriksaan lulus. Jika berjalan dari kode sumber,
gunakan `python run_doxify.py --self-test laporan.txt`.

## Pengaturan

| Pengaturan | Pilihan | Bawaan |
|---|---|---|
| Output | Gabungkan jadi satu PDF / Satu PDF per gambar | Gabungan |
| Ukuran halaman | A4 / Letter / Ukuran asli gambar | A4 |
| Orientasi | Otomatis / Potret / Lanskap | Otomatis |
| Margin | Tanpa / Kecil (10 mm) / Sedang (20 mm) | Kecil |
| Kualitas | Asli / Terkompres | Asli |
| Kualitas JPEG | 30-95 (aktif saat Terkompres) | 75 |
| Hapus metadata | Ya / Tidak | Ya |

Pilihan disimpan otomatis di `%APPDATA%\Doxify\settings.json`. Yang disimpan hanya pilihan di atas dan folder tujuan
terakhir. **Nama file gambarmu tidak pernah disimpan.** Menghapus file itu mengembalikan semua ke bawaan.

## Keamanan dan Privasi

### Yang dijamin oleh desain

- **Tidak memakai jaringan.** Tidak ada kode untuk koneksi keluar, telemetri, analytics, atau pengecek pembaruan.
- **Tidak ada jejak nama file.** Log dan keluaran konsol tidak memuat nama file, dan PDF hasil tidak memuat path
  sumber. Metadata PDF hanya berisi produser dan pembuat "Doxify" serta tanggal pembuatan dan perubahan, tanpa penulis atau judul.
- **Metadata gambar dibuang.** EXIF/GPS, XMP, info kamera, komentar, dan thumbnail tertanam dihapus langsung di
  level byte JPEG tanpa kompres ulang. Hanya tag orientasi yang dipertahankan agar halaman tetap tegak.
- **File sementara bersih.** Disimpan di folder acak berawalan `doxify_`, selalu dihapus, dan sisa akibat crash
  dibersihkan saat aplikasi dibuka lagi.
- **Penulisan atomik.** PDF ditulis ke file sementara lalu di-rename. PDF lama tidak rusak bila penulisan gagal
  atau dibatalkan.
- **File sumber tidak disentuh.** Doxify hanya membaca gambarmu.

### Bagaimana ini diperiksa

Tes otomatis memeriksa hal-hal berikut:

- Konversi tetap berhasil ketika semua panggilan jaringan diblokir, baik di dalam proses maupun di proses
  terpisah yang jaringannya diblokir sejak Python menyala.
- Kode tidak berisi URL atau kata kunci telemetri, dan kode inti tidak mengimpor library jaringan.
- Log dan konsol tidak membocorkan nama file.
- Ribuan file gambar yang sengaja dirusak (fuzzing) tidak menyebabkan crash atau hang.
- Disk penuh, PDF yang sedang dibuka aplikasi lain, pembatalan, dan proses yang di-kill ditangani tanpa merusak
  PDF lama atau meninggalkan file sampah.

Sebagai bukti tambahan yang bisa kamu jalankan sendiri di Windows (PowerShell sebagai Administrator, virtualenv aktif):

```powershell
# Memblokir Python lewat Windows Firewall, memastikan blokirnya efektif, lalu menjalankan semua tes
.\scripts\windows\verify-offline.ps1

# Mencoba GUI secara manual saat jaringan diblokir
.\scripts\windows\block-network.ps1 -Action Add
python -m app.main
.\scripts\windows\block-network.ps1 -Action Remove      # jangan lupa dibuka kembali

# Audit kerentanan library (butuh internet; hanya di komputer pengembangan)
.\scripts\windows\audit-dependencies.ps1
```

Pada `.exe` hasil build, `Doxify.exe --self-test` memantau dan menggagalkan setiap upaya koneksi dari Python
selama pemeriksaan berlangsung.

### Batas jaminan

- Doxify melindungi data dari **layanan pihak ketiga**, bukan dari orang yang memakai komputermu atau dari
  malware di komputermu.
- PDF hasil tidak dienkripsi. Fitur password direncanakan untuk versi mendatang.
- Penghapusan file sementara memakai penghapusan biasa. "Secure wipe" tidak dilakukan karena tidak efektif pada SSD.
- Installer dan `.exe` tidak ditandatangani digital (lihat [Instalasi](#instalasi)).

## Cara Kerja dan Batasan Teknis

### Perlakuan tiap jenis gambar

| Input | Perlakuan |
|---|---|
| JPG, kualitas **Asli** | Data JPEG disalin ke PDF apa adanya (tanpa kompres ulang). Metadata dibuang di level byte. Rotasi EXIF dilakukan lewat rotasi halaman PDF |
| JPG dengan orientasi EXIF "cermin" (nilai 2, 4, 5, 7) | Satu-satunya kasus JPG dikompres ulang (kualitas 95), karena rotasi halaman PDF tidak bisa membalik gambar |
| PNG RGB, grayscale, atau palet tanpa transparansi | Dimasukkan apa adanya (lossless) |
| PNG transparan atau mode lain (mis. 16-bit) | Diratakan ke latar putih lewat Pillow, lalu dimasukkan |
| Semua format, kualitas **Terkompres** | Diubah ke JPEG dengan kualitas pilihanmu, sisi terpanjang dibatasi 3508 px (A4 pada 300 dpi) |

Pada mode **Ukuran asli**, halaman mengikuti dimensi gambar menurut DPI-nya. Gambar tanpa informasi DPI dianggap
96 dpi.

### Batas

| Batas | Nilai | Alasan |
|---|---|---|
| Ukuran satu gambar | 150 megapiksel | Mencegah kehabisan memori |
| Total satu PDF gabungan | 1 GB data gambar | Menjaga puncak RAM wajar (sekitar 1,2 kali ukuran data) |
| Panjang path tujuan | sekitar 240 karakter | Di bawah batas klasik Windows (260) |

Jika melewati batas, Doxify menampilkan pesan yang jelas. Bagi pekerjaan menjadi beberapa PDF.

### Kinerja

Angka berikut diukur di lingkungan pengembangan (Linux), bukan di laptop, jadi gunakan hanya sebagai gambaran.
Jalankan `python scripts\benchmark.py` untuk angka di komputermu sendiri.

| Skenario | Waktu | Memori puncak |
|---|---|---|
| 20 foto sekitar 5 MB, kualitas asli | sekitar 2 detik | sekitar 195 MB |
| 20 foto sekitar 5 MB, terkompres | sekitar 10 detik | sekitar 195 MB |
| 60 foto sekitar 5 MB (PDF 323 MB) | sekitar 6 detik | sekitar 400 MB |

PNG berukuran puluhan MB lebih lambat (sekitar 0,3 detik per MB) karena parser PNG di `img2pdf`. PNG biasa
beberapa MB tetap cepat.

## Arsitektur dan Struktur Proyek

```
GUI (PySide6)  ──►  Worker thread  ──►  ImageConverter  ──►  PDF
   │                                         │
   └── ui/logic.py (tanpa Qt, diuji penuh)   └── utils/: metadata, filenames, temp
```

Prinsip desain:

- **Pemisahan lapisan.** `converters/` dan `utils/` tidak mengimpor apa pun dari `ui/` atau Qt, sehingga inti
  bisa diuji dan dipakai tanpa GUI. Sebuah tes menegakkan aturan ini.
- **Logika UI tanpa Qt.** Daftar file, urutan, ringkasan hasil, dan format ukuran ada di `ui/logic.py` agar bisa
  diuji penuh tanpa membuka jendela. Lapisan Qt dibuat setipis mungkin.
- **Antarmuka converter yang sama.** Setiap format mengimplementasikan `BaseConverter`, sehingga menambah format
  baru cukup menambah satu modul.
- **Pekerjaan berat di thread terpisah** dan melapor lewat signal Qt.

```
doxify/
├── app/
│   ├── main.py                  titik masuk GUI
│   ├── cli.py                   antarmuka command line
│   ├── selftest.py              uji mandiri (--self-test)
│   ├── converters/
│   │   ├── base.py              tipe data, pengaturan, error, antarmuka BaseConverter
│   │   └── image.py             konversi JPG/PNG
│   ├── ui/
│   │   ├── main_window.py       jendela utama
│   │   ├── file_list.py         daftar drag-and-drop + thumbnail
│   │   ├── worker.py            konversi di thread terpisah
│   │   └── logic.py             logika UI tanpa Qt
│   └── utils/
│       ├── metadata.py          hapus metadata JPEG tanpa kompres ulang
│       ├── filenames.py         nama file aman Windows, anti-timpa
│       ├── temp.py              folder temp acak yang selalu dibersihkan
│       └── settings_store.py    penyimpanan pengaturan lokal
├── scripts/
│   ├── benchmark.py             ukur kecepatan dan memori
│   ├── make_icon.py             membuat assets/doxify.ico
│   ├── make_version_info.py     info versi untuk .exe
│   ├── verify_build.py          memeriksa isi hasil build
│   └── windows/                 build.ps1, verify-offline.ps1, block-network.ps1, audit-dependencies.ps1
├── installer/setup.iss          skrip Inno Setup
├── assets/doxify.ico
├── tests/                       tes otomatis
├── run_doxify.py                titik masuk untuk PyInstaller
├── build.spec                   konfigurasi PyInstaller
├── requirements.txt             dependensi runtime
├── requirements-dev.txt         + alat tes
└── requirements-build.txt       alat build
```

## Pengembangan

### Menjalankan tes

```powershell
pip install -r requirements-dev.txt
python -m unittest discover -s tests -t .      # atau: pytest
```

Terdapat lebih dari 200 tes otomatis. Tes GUI (`tests/test_gui_smoke.py`) memakai Qt mode `offscreen`, jadi tidak
ada jendela yang muncul. Tes ini dilewati otomatis bila PySide6 belum terpasang atau Python 3.14 digunakan;
Qt offscreen dengan `QThread` dapat mengabort interpreter Python 3.14. Uji mandiri hasil build tetap memverifikasi
bahwa GUI, plugin gambar, dan konversi berjalan pada executable.

| Berkas tes | Mencakup |
|---|---|
| `test_image_converter.py` | Konversi dasar, tata letak halaman, EXIF, transparansi, kualitas, privasi, mode output |
| `test_hardening.py` | File rusak (fuzzing), disk penuh, PDF terbuka di aplikasi lain, pembatalan, proses di-kill, privasi log |
| `test_offline.py` | Bukti tidak ada pemakaian jaringan, tanpa URL/telemetri, dependensi terkunci |
| `test_metadata.py` | Penghapusan metadata JPEG yang lossless |
| `test_ui_logic.py`, `test_settings_store.py` | Logika daftar file, ringkasan hasil, pengaturan tersimpan, aturan arsitektur |
| `test_filenames.py`, `test_temp.py` | Nama file Windows, folder sementara |
| `test_selftest.py`, `test_packaging.py` | Uji mandiri, installer, spec PyInstaller, pemeriksa build, ikon |
| `test_gui_smoke.py` | Jendela utama, daftar, konversi end-to-end lewat GUI |

### Menambah converter format baru

1. Buat modul baru di `app/converters/`, misalnya `text.py`, dengan mewarisi `BaseConverter`:

   ```python
   from app.converters.base import BaseConverter, ConversionResult

   class TextConverter(BaseConverter):
       extensions = frozenset({".txt"})

       def convert(self, inputs, output, settings=None, progress=None, cancel=None) -> ConversionResult:
           ...
   ```

2. Ikuti kontrak yang sama dengan `ImageConverter`: laporkan progress lewat callback, periksa `cancel`,
   catat kegagalan per file ke `result.failed` (jangan menggagalkan seluruh batch), dan tulis hasil secara atomik.
3. Jangan mengimpor apa pun dari `ui/` atau library jaringan. Tes arsitektur dan tes offline akan menolaknya.
4. Tambahkan tes, termasuk kasus file rusak.

### Konvensi

- Pesan yang ditampilkan ke pengguna ditulis dalam bahasa Indonesia dan tidak memuat path atau nama file di log.
- Nomor versi hanya ada di `app/__init__.py` (dan nilai bawaan `#define AppVersion` di `installer/setup.iss`;
  sebuah tes memastikan keduanya sama).

## Membangun Installer (Rilis)

Prasyarat di komputer pembuat: Python 3.14 dalam virtualenv proyek aktif, `requirements.txt` dan
`requirements-dev.txt` terpasang, serta [Inno Setup](https://jrsoftware.org/isinfo.php) 6.3 atau 7.
Skrip mencari compiler Inno Setup 7 terlebih dahulu, lalu versi 6. Internet hanya diperlukan untuk memasang
alat build (PyInstaller), bukan untuk aplikasinya.

```powershell
.\scripts\windows\build.ps1                  # alur lengkap
.\scripts\windows\build.ps1 -SkipInstaller   # tanpa Inno Setup (folder dan ZIP portabel saja)
```

Langkah yang dijalankan (berhenti di langkah yang gagal):

1. Tes otomatis
2. PyInstaller (mode folder, tanpa UPX, tanpa konsol, modul jaringan dikecualikan)
3. Pemeriksaan isi paket (`scripts/verify_build.py`), yang gagal bila `Qt6Network.dll` atau `_ssl.pyd` ikut terbungkus
   atau plugin Qt yang wajib hilang
4. Uji mandiri pada `Doxify.exe`
5. ZIP portabel
6. Installer Inno Setup
7. Hash SHA-256 dan catatan versi library

Hasil di folder `dist\`:

| Berkas | Isi |
|---|---|
| `Doxify\` | Folder aplikasi |
| `Doxify-Portable-<versi>.zip` | Versi portabel |
| `installer\Doxify-Setup-<versi>.exe` | Installer |
| `SHA256SUMS.txt` | Hash untuk memverifikasi berkas |
| `build-info.txt` | Versi semua library yang terpasang saat build, sebagai jejak yang bisa diulang |

**Menaikkan versi:** ubah `__version__` di `app/__init__.py` dan nilai bawaan `#define AppVersion` di
`installer/setup.iss`. **Jangan pernah mengubah `AppId`** di `setup.iss`: nilai itu yang membuat memasang ulang
berfungsi sebagai pembaruan.

### Uji pasang dan hapus

Sebelum membagikan rilis, uji di Windows yang bersih. Paling mudah memakai Windows Sandbox (Windows 10/11 Pro,
aktifkan di "Turn Windows features on or off"):

1. Jalankan installer. Tidak boleh ada prompt UAC.
2. Pastikan terpasang di `%LOCALAPPDATA%\Programs\Doxify` dan shortcut Start Menu muncul.
3. Buka Doxify, konversi beberapa gambar, dan simpan PDF.
4. Jalankan installer lagi (versi sama, lalu versi baru). Harus menjadi pembaruan tanpa entri ganda di Apps.
5. Uninstall. Folder aplikasi dan sisa `doxify_*` di folder temp hilang, gambar dan PDF-mu utuh.

## Pemecahan Masalah

| Gejala | Kemungkinan penyebab dan solusi |
|---|---|
| SmartScreen: "Windows protected your PC" | Installer tidak ditandatangani digital. Klik **More info > Run anyway** |
| Defender menghapus atau memblokir `Doxify.exe` | False positive pada hasil PyInstaller. Tambahkan pengecualian untuk folder instalasi, lalu pasang ulang |
| "File tujuan sedang dipakai aplikasi lain" | PDF dengan nama itu sedang terbuka di aplikasi lain. Tutup dulu, atau pilih nama lain. PDF lama tidak rusak |
| "Disk penuh" | Kosongkan ruang di drive tujuan lalu ulangi |
| "Path folder tujuan terlalu panjang" | Pilih folder yang lebih pendek, mis. langsung di Documents |
| File dilewati: "File rusak atau bukan gambar yang valid" | Isi file memang tidak valid (terpotong, rusak, atau ekstensi palsu). Buka file itu di aplikasi lain untuk memastikan |
| File ditolak: "Format tidak didukung" | v1.0 hanya mendukung `.jpg`, `.jpeg`, `.png` |
| "Gambar terlalu besar" | Melebihi 150 megapiksel. Perkecil gambar lebih dulu |
| "Total ukuran gambar terlalu besar untuk satu PDF" | Melebihi 1 GB. Bagi menjadi beberapa PDF |
| Thumbnail tidak muncul | Hanya tampilan. Konversi tetap bekerja. Jalankan `Doxify.exe --self-test` untuk memeriksa plugin gambar Qt |
| Konversi PNG yang sangat besar terasa lambat | Normal, lihat bagian [Kinerja](#kinerja) |
| `Activate.ps1` ditolak | Jalankan `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Aplikasi gagal dibuka setelah build | Jalankan `Doxify.exe --self-test laporan.txt` dan baca `laporan.txt` untuk melihat pemeriksaan mana yang gagal |

Jika masalah berlanjut, sertakan isi `laporan.txt` dari `--self-test` saat melaporkan masalah.

## Roadmap

| Versi | Rencana |
|---|---|
| v1.0 | JPG/PNG ke PDF, GUI desktop, pengaturan halaman, keamanan dasar, installer (**saat ini**) |
| v1.1 | Format gambar tambahan (WEBP, BMP, TIFF), teks dan HTML ke PDF |
| v1.2 | DOCX/PPTX/XLSX ke PDF lewat LibreOffice atau Microsoft Office yang sudah terpasang |
| v2.0 | Fitur PDF: merge, split, kompres, proteksi password |

Gagasan yang belum dijadwalkan: perakitan PDF bertahap untuk batch yang sangat besar, tanda tangan digital pada
installer, dan wizard installer berbahasa Indonesia.

## Lisensi dan Kredit

**Lisensi proyek belum ditentukan.** Tambahkan berkas `LICENSE` sebelum membagikan kode atau installer ke orang lain.

Doxify dibangun di atas library open source berikut. Periksa persyaratan lisensi masing-masing, terutama bila kamu
mendistribusikan aplikasi ini (misalnya PySide6 dan `img2pdf` dilisensikan di bawah LGPL):

- [PySide6 / Qt for Python](https://doc.qt.io/qtforpython-6/)
- [img2pdf](https://gitlab.mister-muffin.de/josch/img2pdf)
- [Pillow](https://python-pillow.org/)
- [pikepdf](https://github.com/pikepdf/pikepdf)
- [PyInstaller](https://pyinstaller.org/)
- [Inno Setup](https://jrsoftware.org/isinfo.php)
