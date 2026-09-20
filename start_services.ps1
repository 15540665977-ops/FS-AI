# 谱图智能分析系统 — 后台启动脚本
# 由“启动系统.bat”或用户启动文件夹快捷方式调用

$projectRoot = $PSScriptRoot
$backendDir = Join-Path $projectRoot "backend"
$frontendDir = Join-Path $projectRoot "frontend"
$logDir = Join-Path $projectRoot "logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { (Get-Command python -ErrorAction Stop).Source }
$npm = (Get-Command npm.cmd -ErrorAction Stop).Source

function Test-PortListening {
    param([int]$Port)
    return $null -ne (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

# ---------- 后端 (FastAPI, 端口 8000) ----------
if (Test-PortListening 8000) {
    Write-Host "[skip] Backend is already running (port 8000 is in use)."
} else {
    Start-Process -FilePath $python `
        -ArgumentList "main.py" `
        -WorkingDirectory $backendDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $backendDir "start.log") `
        -RedirectStandardError (Join-Path $backendDir "error.log")
    Write-Host "[start] Backend service is starting."
}

# ---------- 前端 (Vite, 端口 5173) ----------
if (Test-PortListening 5173) {
    Write-Host "[skip] Frontend is already running (port 5173 is in use)."
} else {
    Start-Process -FilePath $npm `
        -ArgumentList "run", "dev:lan" `
        -WorkingDirectory $frontendDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $frontendDir "start.log") `
        -RedirectStandardError (Join-Path $frontendDir "error.log")
    Write-Host "[start] Frontend service is starting."
}
