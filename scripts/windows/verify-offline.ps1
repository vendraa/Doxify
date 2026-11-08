<#
.SYNOPSIS
  Verifikasi offline Doxify memakai Windows Firewall (Fase 3, NFR-01).

.DESCRIPTION
  1. Membuat aturan firewall yang MEMBLOKIR semua koneksi masuk dan keluar untuk Python
     yang dipakai Doxify.
  2. Memastikan aturan itu benar-benar bekerja (Python tidak bisa konek, sementara
     program lain di komputer yang sama bisa).
  3. Menjalankan seluruh tes otomatis dan satu konversi CLI dalam keadaan terblokir.
  4. Menghapus aturan firewall, apa pun hasilnya.

  Harus dijalankan dari PowerShell yang dibuka dengan "Run as administrator",
  di folder proyek (yang berisi folder app dan tests), dengan virtualenv aktif.

.EXAMPLE
  .\scripts\windows\verify-offline.ps1
#>
[CmdletBinding()]
param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$RuleName = "Doxify - blokir jaringan (uji offline)"

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($id)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Remove-DoxifyRules {
    Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
}

if (-not (Test-Admin)) {
    Write-Error "Jalankan PowerShell sebagai Administrator (klik kanan, Run as administrator)."
    exit 1
}
if (-not (Test-Path ".\app") -or -not (Test-Path ".\tests")) {
    Write-Error "Jalankan skrip ini dari folder proyek Doxify (yang berisi folder app dan tests)."
    exit 1
}

# Virtualenv memakai peluncur (launcher): proses Python yang sebenarnya berjalan adalah
# interpreter dasar. Maka KEDUA path diblokir supaya aturan pasti mengenai prosesnya.
$paths = & $Python -c "import sys; print(sys.executable); print(sys.base_executable)"
$targets = @($paths | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique)
if ($targets.Count -eq 0) {
    Write-Error "Python tidak ditemukan. Aktifkan virtualenv atau isi parameter -Python."
    exit 1
}

$exitCode = 0
try {
    Remove-DoxifyRules
    foreach ($target in $targets) {
        New-NetFirewallRule -DisplayName $RuleName -Direction Outbound -Action Block -Program $target -Profile Any | Out-Null
        New-NetFirewallRule -DisplayName $RuleName -Direction Inbound  -Action Block -Program $target -Profile Any | Out-Null
        Write-Host "Diblokir: $target"
    }

    # Tahap 2: pastikan aturan bekerja. Pembanding = PowerShell (program lain, tidak diblokir).
    $others = (Test-NetConnection -ComputerName "1.1.1.1" -Port 53 -WarningAction SilentlyContinue).TcpTestSucceeded
    $probe = "import socket`ntry:`n    socket.create_connection(('1.1.1.1', 53), timeout=4)`n    print('CONNECTED')`nexcept OSError:`n    print('BLOCKED')"
    $result = (& $Python -c $probe | Select-Object -Last 1)
    if ($result -eq "CONNECTED") {
        Write-Host "GAGAL: Python masih bisa konek ke internet, aturan firewall tidak efektif." -ForegroundColor Red
        $exitCode = 2
    }
    else {
        if ($others) {
            Write-Host "OK: program lain bisa konek, Python tidak. Aturan firewall bekerja." -ForegroundColor Green
        }
        else {
            Write-Host "CATATAN: komputer ini tampaknya memang sedang offline, jadi tahap ini belum membuktikan aturan firewall bekerja." -ForegroundColor Yellow
            Write-Host "         Sambungkan ke internet lalu jalankan ulang untuk bukti yang kuat." -ForegroundColor Yellow
        }

        # Tahap 3: semua tes + satu konversi nyata dalam keadaan terblokir
        Write-Host "`nMenjalankan seluruh tes otomatis..." -ForegroundColor Cyan
        & $Python -m unittest discover -s tests -t .
        if ($LASTEXITCODE -ne 0) { $exitCode = 3 }

        $work = Join-Path $env:TEMP ("doxify_offline_" + [guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Path $work | Out-Null
        $gen = "from PIL import Image`nImage.new('RGB', (800, 600), (30, 90, 160)).save(r'$work\a.jpg')`nImage.new('RGBA', (400, 400), (200, 20, 20, 120)).save(r'$work\b.png')"
        & $Python -c $gen
        & $Python -m app.cli "$work\a.jpg" "$work\b.png" -o "$work\hasil.pdf"
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path "$work\hasil.pdf")) { $exitCode = 4 }
        Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
    }
}
finally {
    Remove-DoxifyRules
    Write-Host "`nAturan firewall sementara sudah dihapus."
}

if ($exitCode -eq 0) {
    Write-Host "`nHASIL: LULUS. Doxify bekerja penuh saat jaringan diblokir." -ForegroundColor Green
    Write-Host "Untuk menguji GUI-nya juga: jalankan skrip ini lagi dengan aturan ditahan (lihat README), lalu buka python -m app.main."
}
else {
    Write-Host "`nHASIL: GAGAL (kode $exitCode). Lihat pesan di atas." -ForegroundColor Red
}
exit $exitCode
