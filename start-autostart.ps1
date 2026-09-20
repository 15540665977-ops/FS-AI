$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$logDir = Join-Path $projectRoot "logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logPath = Join-Path $logDir "autostart.log"
"[$timestamp] Login autostart invoked." | Out-File -LiteralPath $logPath -Append -Encoding utf8

& (Join-Path $projectRoot "start_services.ps1")
