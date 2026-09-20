$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$startupDir = [Environment]::GetFolderPath([Environment+SpecialFolder]::Startup)
$shortcutName = "Spectral Analysis System - Login Autostart.lnk"
$shortcutPath = Join-Path $startupDir $shortcutName
$launcherPath = Join-Path $projectRoot "start-autostart.ps1"

if (-not (Test-Path -LiteralPath $launcherPath)) {
    throw "Cannot find autostart launcher: $launcherPath"
}

$wscript = New-Object -ComObject WScript.Shell
$shortcut = $wscript.CreateShortcut($shortcutPath)
$shortcut.TargetPath = (Get-Command powershell.exe -ErrorAction Stop).Source
$shortcut.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$launcherPath`""
$shortcut.WorkingDirectory = $projectRoot
$shortcut.Description = "Start the spectral analysis system after this user signs in."
$shortcut.WindowStyle = 7
$shortcut.Save()

Write-Host "Configured login autostart for the current Windows user."
Write-Host "Shortcut: $shortcutPath"
Write-Host "Target: $($shortcut.TargetPath) $($shortcut.Arguments)"
