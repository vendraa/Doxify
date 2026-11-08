<#
.SYNOPSIS
  Memeriksa kerentanan yang diketahui pada library yang terpasang (bagian 9 PRD).

.DESCRIPTION
  Memakai pip-audit. Skrip ini butuh internet karena membandingkan versi library
  dengan database kerentanan. Ini hanya dijalankan di komputer pengembangan; aplikasi
  Doxify sendiri tidak pernah memakai jaringan. Jalankan sebelum membuat build rilis,
  dengan virtualenv proyek aktif.
#>
$ErrorActionPreference = "Stop"
python -m pip install --upgrade pip-audit
Write-Host "`nMemeriksa library yang terpasang di virtualenv ini..." -ForegroundColor Cyan
python -m pip_audit
if ($LASTEXITCODE -eq 0) {
    Write-Host "`nTidak ada kerentanan yang diketahui." -ForegroundColor Green
}
else {
    Write-Host "`nAda temuan. Perbarui library yang disebut, jalankan ulang tes, lalu kunci versi baru di requirements.txt." -ForegroundColor Yellow
}
exit $LASTEXITCODE
