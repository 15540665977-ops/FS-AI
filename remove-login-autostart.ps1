$ErrorActionPreference = "Stop"

$startupDir = [Environment]::GetFolderPath([Environment+SpecialFolder]::Startup)
$shortcutName = "Spectral Analysis System - Login Autostart.lnk"
$shortcutPath = Join-Path $startupDir $shortcutName

if (Test-Path -LiteralPath $shortcutPath) {
    Remove-Item -LiteralPath $shortcutPath -Force
    Write-Host "Removed login autostart shortcut: $shortcutPath"
} else {
    Write-Host "Login autostart shortcut was not configured: $shortcutPath"
}
