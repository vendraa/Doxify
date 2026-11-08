<#
.SYNOPSIS
  Menahan aturan firewall pemblokir jaringan untuk Python, agar kamu bisa mencoba
  GUI Doxify secara manual dalam keadaan terblokir. Hapus setelah selesai.

.EXAMPLE
  .\scripts\windows\block-network.ps1 -Action Add      # blokir
  python -m app.main                                   # coba semua fitur secara manual
  .\scripts\windows\block-network.ps1 -Action Remove   # buka blokir
  .\scripts\windows\block-network.ps1 -Action Status   # lihat status

  Harus dijalankan sebagai Administrator (kecuali -Action Status).
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet("Add", "Remove", "Status")][string]$Action,
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$RuleName = "Doxify - blokir jaringan (uji offline)"

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($id)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if ($Action -ne "Status" -and -not (Test-Admin)) {
    Write-Error "Jalankan PowerShell sebagai Administrator."
    exit 1
}

switch ($Action) {
    "Add" {
        $paths = & $Python -c "import sys; print(sys.executable); print(sys.base_executable)"
        $targets = @($paths | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique)
        if ($targets.Count -eq 0) { Write-Error "Python tidak ditemukan."; exit 1 }
        Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
        foreach ($target in $targets) {
            New-NetFirewallRule -DisplayName $RuleName -Direction Outbound -Action Block -Program $target -Profile Any | Out-Null
            New-NetFirewallRule -DisplayName $RuleName -Direction Inbound  -Action Block -Program $target -Profile Any | Out-Null
            Write-Host "Diblokir: $target"
        }
        Write-Host "Selesai. JANGAN LUPA hapus aturan ini setelah uji: -Action Remove"
    }
    "Remove" {
        Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
        Write-Host "Aturan firewall uji sudah dihapus."
    }
    "Status" {
        $rules = Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue
        if ($rules) { Write-Host "Aturan pemblokir AKTIF ($(@($rules).Count) aturan)." }
        else { Write-Host "Tidak ada aturan pemblokir." }
    }
}
