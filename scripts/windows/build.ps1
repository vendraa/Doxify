<#
.SYNOPSIS
  Membangun Doxify untuk rilis: .exe (PyInstaller), ZIP portabel, installer (Inno Setup), dan hash SHA-256.

.DESCRIPTION
  Langkah (berhenti di langkah yang gagal):
   1. tes otomatis                       (lewati dengan -SkipTests)
   2. PyInstaller (mode folder)          -> dist\Doxify\
   3. pemeriksaan isi paket              (scripts\verify_build.py)
   4. uji mandiri pada Doxify.exe        (membuka Qt, mengonversi gambar, memantau jaringan)
   5. ZIP portabel                       -> dist\Doxify-Portable-<versi>.zip
   6. installer Inno Setup               -> dist\installer\Doxify-Setup-<versi>.exe  (lewati dengan -SkipInstaller)
   7. SHA256SUMS.txt dan build-info.txt  (daftar versi library yang dipakai, untuk jejak build)

  Prasyarat (di komputer pengembangan, butuh internet hanya untuk memasang alat build):
   - Python 3.14 dalam virtualenv proyek, dengan `requirements.txt` dan `requirements-dev.txt` terpasang
   - Inno Setup 6.3 atau 7 (https://jrsoftware.org/isinfo.php), untuk langkah 6
  Jalankan dari folder proyek:  .\scripts\windows\build.ps1

.EXAMPLE
  .\scripts\windows\build.ps1
  .\scripts\windows\build.ps1 -SkipInstaller
#>
[CmdletBinding()]
param(
    [string]$Python = "python",
    [switch]$SkipTests,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"

function Step($text) { Write-Host "`n=== $text ===" -ForegroundColor Cyan }
function Fail($text) { Write-Host "GAGAL: $text" -ForegroundColor Red; exit 1 }
function Check-Exit($what) { if ($LASTEXITCODE -ne 0) { Fail "$what (kode keluar $LASTEXITCODE)" } }

if (-not (Test-Path ".\app") -or -not (Test-Path ".\build.spec")) {
    Fail "Jalankan dari folder proyek Doxify (yang berisi folder app dan berkas build.spec)."
}

# Beberapa distribusi Python Windows memakai konfigurasi isolated yang tidak
# menambahkan direktori kerja ke sys.path. Pastikan paket proyek tetap dapat diimpor.
$projectRoot = (Resolve-Path ".").Path
if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$projectRoot;$env:PYTHONPATH"
} else {
    $env:PYTHONPATH = $projectRoot
}

$versionOutput = & $Python -c "from app import __version__; print(__version__)"
Check-Exit "membaca versi"
$version = ($versionOutput | Out-String).Trim()
if (-not $version) { Fail "versi aplikasi kosong." }
Write-Host "Membangun Doxify $version" -ForegroundColor Green

# Alat build (PyInstaller) dipasang di virtualenv; hanya langkah ini yang butuh internet.
& $Python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('PyInstaller') else 1)"
if ($LASTEXITCODE -ne 0) {
    Step "Memasang PyInstaller (butuh internet, hanya di komputer pengembangan)"
    & $Python -m pip install -r requirements-build.txt
    Check-Exit "pip install PyInstaller"
}

if (-not $SkipTests) {
    Step "1. Tes otomatis"
    & $Python -m unittest discover -s tests -t .
    Check-Exit "tes otomatis"
}

Step "2. PyInstaller"
if (Test-Path ".\dist\Doxify") { Remove-Item -Recurse -Force ".\dist\Doxify" }
& $Python -m PyInstaller --noconfirm --clean build.spec
Check-Exit "PyInstaller"
$exe = ".\dist\Doxify\Doxify.exe"
if (-not (Test-Path $exe)) { Fail "Doxify.exe tidak terbentuk." }

Step "3. Pemeriksaan isi paket"
& $Python scripts\verify_build.py dist\Doxify
Check-Exit "pemeriksaan isi paket"

Step "4. Uji mandiri pada Doxify.exe"
$report = Join-Path (Resolve-Path ".\dist").Path "selftest.txt"
if (Test-Path $report) { Remove-Item $report }
$proc = Start-Process -FilePath $exe -ArgumentList "--self-test `"$report`"" -Wait -PassThru
if (Test-Path $report) { Get-Content $report } else { Write-Host "(laporan tidak terbentuk)" }
if ($proc.ExitCode -ne 0) { Fail "uji mandiri gagal (kode keluar $($proc.ExitCode)). Lihat laporan di atas." }

Step "5. ZIP portabel"
$zip = ".\dist\Doxify-Portable-$version.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path ".\dist\Doxify" -DestinationPath $zip
Write-Host "Dibuat: $zip"

$installer = $null
if ($SkipInstaller) {
    Write-Host "`n(Langkah installer dilewati.)" -ForegroundColor Yellow
}
else {
    Step "6. Installer Inno Setup"
    $candidates = @(
        "$env:ProgramFiles\Inno Setup 7\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )
    $iscc = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    if (-not $iscc) {
        Write-Host "Inno Setup 6 atau 7 tidak ditemukan. Pasang dari https://jrsoftware.org/isinfo.php lalu jalankan ulang," -ForegroundColor Yellow
        Write-Host "atau pakai -SkipInstaller. ZIP portabel sudah jadi." -ForegroundColor Yellow
    }
    else {
        & $iscc "/DAppVersion=$version" ".\installer\setup.iss"
        Check-Exit "Inno Setup"
        $installer = ".\dist\installer\Doxify-Setup-$version.exe"
        if (-not (Test-Path $installer)) { Fail "Installer tidak terbentuk." }
    }
}

Step "7. Hash SHA-256 dan catatan build"
$sums = @()
foreach ($file in @($zip, $installer)) {
    if ($file -and (Test-Path $file)) {
        $h = Get-FileHash -Algorithm SHA256 -Path $file
        $sums += ("{0}  {1}" -f $h.Hash.ToLower(), (Split-Path $file -Leaf))
    }
}
$sums | Set-Content -Encoding ascii ".\dist\SHA256SUMS.txt"
$sums | ForEach-Object { Write-Host $_ }
@("Doxify $version", "Dibangun: $(Get-Date -Format s)", (& $Python --version), "", "Library terpasang:") +
    (& $Python -m pip freeze) | Set-Content -Encoding utf8 ".\dist\build-info.txt"

Write-Host "`nSELESAI. Hasil ada di folder dist\" -ForegroundColor Green
if ($installer) { Write-Host "  Installer : $installer" }
Write-Host "  Portabel  : $zip"
Write-Host "Langkah berikutnya: uji pasang dan hapus di mesin bersih (lihat README, bagian Fase 4)."
